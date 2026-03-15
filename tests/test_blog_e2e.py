"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.

Requires either:
  1. session_state.json (preferred), or
  2. NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env

Run:
    pytest tests/test_blog_e2e.py -m e2e -v
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v   # publish test only
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from automator.config import browser_settings
from automator.options import AccountOption, TitleOption, ContentOption, MetaOption, RunSetting
from automator.selector_loader import SelectorLoader

# Structural constants (iframe path + editor root) — not selector-dependent
_MAIN_FRAME    = "#mainFrame"
_EDITOR_BODY   = ".se-content"

# Load selector JSON once for e2e helpers
_LOGIN_SEL  = SelectorLoader.load("selectors/naver/login.json")
_EDITOR_SEL = SelectorLoader.load("selectors/naver/editor.json")
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID", "")
NAVER_PW      = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH", "session_state.json")
IMAGE_PATH    = os.getenv("TEST_IMAGE_PATH", "images/preview_1.png")

# Images for test_full_post_sequence
# Set these in .env to use real images in the publish test.
# e.g. TEST_PREVIEW_1=images/math_1.jpg
#      TEST_PREVIEW_2=images/math_2.jpg
#      TEST_THUMBNAIL_1=images/thumb_base.jpg
TEST_PREVIEW_1    = os.getenv("TEST_PREVIEW_1", "")
TEST_PREVIEW_2    = os.getenv("TEST_PREVIEW_2", "")
TEST_PREVIEW_3    = os.getenv("TEST_PREVIEW_3", "")
TEST_THUMBNAIL_1  = os.getenv("TEST_THUMBNAIL_1", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def account() -> AccountOption:
    if not NAVER_BLOG_ID:
        if not os.path.exists(SESSION_PATH):
            pytest.skip("Set NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env")
    return AccountOption(
        naver_id=NAVER_ID,
        naver_pw=NAVER_PW,
        blog_id=NAVER_BLOG_ID,
        session_path=SESSION_PATH,
    )


@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser, account: AccountOption):
    if os.path.exists(account.resolved_session_path):
        ctx = browser_instance.new_context(storage_state=account.resolved_session_path)
    else:
        ctx  = browser_instance.new_context()
        page = ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        _LOGIN_SEL.locator(page, "naver_login_id").fill(account.naver_id)
        _LOGIN_SEL.locator(page, "naver_login_pw").fill(account.naver_pw)
        _LOGIN_SEL.locator(page, "naver_login_submit").click()
        page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
        ctx.storage_state(path=account.resolved_session_path)
        page.close()

    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext):
    p = auth_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor(page: Page, account: AccountOption) -> SmartEditorOne:
    # dry_run=True is the SmartEditorOne default — publish() is always a no-op in tests.
    return SmartEditorOne(page, account.write_url)


@pytest.fixture(scope="session")
def post_images() -> tuple:
    """
    .env의 TEST_PREVIEW_1~3, TEST_THUMBNAIL_1 경로를 반환.
    미설정 또는 파일 없으면 테스트를 skip한다.
    """
    paths = (TEST_PREVIEW_1, TEST_PREVIEW_2, TEST_PREVIEW_3, TEST_THUMBNAIL_1)
    missing = [p for p in paths if not p or not os.path.exists(p)]
    if missing:
        pytest.skip(
            f"test_full_post_sequence requires TEST_PREVIEW_1~3 and "
            f"TEST_THUMBNAIL_1 in .env. Missing: {missing}"
        )
    return paths


# ---------------------------------------------------------------------------
# E2E: Editor loads
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page, account: AccountOption):
    page.goto(account.write_url)
    page.frame_locator(_MAIN_FRAME) \
        .locator(_EDITOR_BODY) \
        .wait_for(state="visible", timeout=15_000)

@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(editor: SmartEditorOne, page: Page):
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")
    editor.open()
    editor.upload_image(IMAGE_PATH)
    assert page.frame_locator(_MAIN_FRAME).first.locator(_EDITOR_SEL.css("editor_image")).first.is_visible()


# ---------------------------------------------------------------------------
# E2E: Representative image
# ---------------------------------------------------------------------------

def _upload_three(editor, page):
    editor.open()
    for i in range(3):
        if i > 0: editor.move_cursor_to_end()
        editor.upload_image(IMAGE_PATH)
    page.frame_locator(_MAIN_FRAME).first \
        .locator(_EDITOR_SEL.css("editor_image")).nth(2) \
        .wait_for(state="visible", timeout=15_000)
    assert page.frame_locator(_MAIN_FRAME).first.locator(_EDITOR_SEL.css("editor_image_rep")).count() == 3


def _assert_selected(page, index, total):
    frame   = page.frame_locator(_MAIN_FRAME).first
    buttons = frame.locator(_EDITOR_SEL.css("editor_image_rep"))
    assert frame.locator(_EDITOR_SEL.css("editor_image_rep_selected")).count() == 1
    for i in range(total):
        classes = buttons.nth(i).get_attribute("class") or ""
        if i == index: assert "se-is-selected" in classes
        else:          assert "se-is-selected" not in classes


@pytest.mark.e2e
def test_set_first_image_as_representative(editor, page):
    if not os.path.exists(IMAGE_PATH): pytest.skip()
    _upload_three(editor, page)
    editor.set_representative_image(0)
    _assert_selected(page, 0, 3)


@pytest.mark.e2e
def test_set_second_image_as_representative(editor, page):
    if not os.path.exists(IMAGE_PATH): pytest.skip()
    _upload_three(editor, page)
    editor.set_representative_image(1)
    _assert_selected(page, 1, 3)


@pytest.mark.e2e
def test_set_third_image_as_representative(editor, page):
    if not os.path.exists(IMAGE_PATH): pytest.skip()
    _upload_three(editor, page)
    editor.set_representative_image(2)
    _assert_selected(page, 2, 3)


# ===========================================================================
# E2E Pipeline Tests
#
# 모든 파이프라인 테스트는 dry_run=True (editor fixture 기본값) 상태에서
# 실행되므로 실제 발행은 일어나지 않습니다.
#
# 시나리오 구성:
#   [이미지 필요] TEST_PREVIEW_1~3, TEST_THUMBNAIL_1 (.env 설정 필요)
#   [이미지 불필요] 텍스트 전용 / 예약 발행 검증용
#
# Run all pipeline tests:
#   pytest tests/test_blog_e2e.py -m "e2e and slow" -v
#
# Run a single scenario:
#   pytest tests/test_blog_e2e.py::test_pipeline_default -m "e2e" -v -s
# ===========================================================================


# ---------------------------------------------------------------------------
# Scenario 1: 기본 — 과외, 지역+과목+학습형태+솔트, full layout  (기존 test_full_post_sequence)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_default(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    [Pipeline 1/8] 기본 시나리오 — "대치동 수학 과외" 타겟 포스팅.

    Options
    -------
    - TitleOption  : template="지역+과목+학습형태+솔트", learning_type="과외", include_suffix=True
    - ContentOption: Image×3 → Paragraph 1 → Thumbnail → Paragraph 2, 3
    - MetaOption   : 즉시 발행 (기본값)
    - RunSetting   : 기본값
    """
    preview_1, preview_2, preview_3, thumbnail_1 = post_images

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            preview_images=[preview_1, preview_2, preview_3],
            thumbnail_images=[thumbnail_1],
            layout=[
                "Image 1",
                "Image 2",
                "Image 3",
                "Paragraph 1",
                "Thumbnail 1",
                "Paragraph 2",
                "Paragraph 3",
            ],
            paragraph_prompt=(
                "대치동 수학 과외를 홍보하는 학부모 대상 블로그 글을 작성해주세요. "
                "신뢰감 있고 따뜻한 톤으로, 실제 학부모가 쓴 것처럼 자연스럽게 작성해주세요."
            ),
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 2: 학원 타겟 — learning_type="학원", include_suffix=False (base_name)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_hagwon(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    [Pipeline 2/8] 학원 타겟 시나리오.

    Options
    -------
    - TitleOption  : learning_type="학원", include_suffix=False → base_name 사용
                     e.g. "대치 수학 학원 강력 추천" (suffix 없이 짧은 지역명)
    - ContentOption: Image 1 → Paragraph 1 → Thumbnail 1 → Paragraph 2
    - MetaOption   : 즉시 발행 (기본값)
    """
    preview_1, _, _, thumbnail_1 = post_images

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="학원",
            include_suffix=False,
        ))
        .with_content(ContentOption(
            preview_images=[preview_1],
            thumbnail_images=[thumbnail_1],
            layout=[
                "Image 1",
                "Paragraph 1",
                "Thumbnail 1",
                "Paragraph 2",
            ],
            paragraph_prompt=(
                "대치동 수학 학원을 홍보하는 학부모 대상 블로그 글을 작성해주세요. "
                "학원의 체계적인 커리큘럼과 성적 향상 사례를 중심으로 작성해주세요."
            ),
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 3: 솔트 앞 — template="솔트+지역+과목+학습형태"
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_salt_first(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    [Pipeline 3/8] 솔트 앞 제목 조합.

    Options
    -------
    - TitleOption: template="솔트+지역+과목+학습형태"
                   → e.g. "강력 추천 대치동 수학 과외"
                   솔트를 앞에 두면 검색 노출 패턴이 달라져 스팸 탐지 우회에 유리.
    - ContentOption: Image×2 → Thumbnail → Paragraph×2
    """
    preview_1, preview_2, _, thumbnail_1 = post_images

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="솔트+지역+과목+학습형태",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            preview_images=[preview_1, preview_2],
            thumbnail_images=[thumbnail_1],
            layout=[
                "Image 1",
                "Image 2",
                "Thumbnail 1",
                "Paragraph 1",
                "Paragraph 2",
            ],
            paragraph_prompt=(
                "강남 영어 과외를 홍보하는 블로그 글을 작성해주세요. "
                "원어민 수준의 회화와 내신 대비를 동시에 잡는 커리큘럼을 강조해주세요."
            ),
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 4: 고정 제목 — fixed_title (TitleGenerator 우회)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_fixed_title(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    [Pipeline 4/8] 고정 제목 시나리오.

    Options
    -------
    - TitleOption: fixed_title="목동 수학 과외 후기 강추" → TitleGenerator를 완전히 우회.
                   A/B 테스트나 특정 키워드를 정확히 타겟할 때 사용.
    - ContentOption: Paragraph 1 → Image 1 → Thumbnail 1 → Paragraph 2
                     (단락을 이미지보다 먼저 배치하는 레이아웃)
    """
    preview_1, _, _, thumbnail_1 = post_images

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            fixed_title="목동 수학 과외 후기 강추",
        ))
        .with_content(ContentOption(
            preview_images=[preview_1],
            thumbnail_images=[thumbnail_1],
            layout=[
                "Paragraph 1",
                "Image 1",
                "Thumbnail 1",
                "Paragraph 2",
            ],
            paragraph_prompt=(
                "목동 수학 과외 후기를 작성해주세요. "
                "실제 학부모 입장에서 성적 향상 경험을 생생하게 서술해주세요."
            ),
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 5: 텍스트 전용 — 이미지 없음, 단락만 (post_images 불필요)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_text_only(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    [Pipeline 5/8] 텍스트 전용 시나리오 — 이미지 없음.

    Options
    -------
    - ContentOption: Paragraph×3 레이아웃 (이미지·썸네일 없음)
    - 용도: 이미지가 준비되지 않은 상황, 또는 텍스트 SEO 집중 포스팅.
    - post_images fixture 불필요 — .env IMAGE_PATH 없어도 실행 가능.
    """
    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            layout=[
                "Paragraph 1",
                "Paragraph 2",
                "Paragraph 3",
            ],
            paragraph_prompt=(
                "송파구 국어 과외를 홍보하는 블로그 글을 작성해주세요. "
                "논술 및 수능 국어 대비를 중심으로 학부모의 공감을 이끌어내주세요."
            ),
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 6: 최소 레이아웃 — 단락 1개, 이미지 없음 (post_images 불필요)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_minimal(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    [Pipeline 6/8] 최소 레이아웃 시나리오.

    Options
    -------
    - ContentOption: layout=[] → 빈 레이아웃. 단락 플레이스홀더 1개만 삽입.
    - 용도: 에디터 기본 동작(open → write_title → publish) 전체 경로 최소 검증.
    - MetaOption   : 기본값 (즉시 발행)
    """
    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            fixed_title="테스트 포스트 — 최소 레이아웃",
        ))
        .with_content(ContentOption())  # empty layout
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 7: 예약 발행 (fixed) — schedule_mode="fixed"
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_scheduled_fixed(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    [Pipeline 7/8] 고정 예약 발행 시나리오.

    Options
    -------
    - MetaOption: schedule_mode="fixed", schedule_at=지금+2시간
    - 에디터가 예약 라디오를 클릭하고 시/분 select를 설정하는 UI 흐름 검증.
    - dry_run=True이므로 "발행하기" 버튼은 눌리지 않음.
      → 발행 팝오버가 열린 채로 유지됨. 수동으로 닫거나 그냥 두면 됨.
    - post_images fixture 불필요.
    """
    from datetime import datetime, timedelta
    from automator.options import KST

    # 현재 시각 기준 2시간 뒤, 분을 10의 배수로 맞춰 UI 오차 없게 설정
    now    = datetime.now(tz=KST)
    target = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0) \
             + timedelta(hours=2)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            layout=["Paragraph 1", "Paragraph 2"],
            paragraph_prompt=(
                "마포구 영어 과외를 홍보하는 블로그 글을 작성해주세요. "
                "원어민 발음 교정과 영어 독해 향상을 핵심으로 작성해주세요."
            ),
        ))
        .with_meta(MetaOption(
            schedule_mode="fixed",
            schedule_at=target,
        ))
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True


# ---------------------------------------------------------------------------
# Scenario 8: 예약 발행 (random_window) — schedule_mode="random_window"
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_scheduled_random_window(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    [Pipeline 8/8] 랜덤 윈도우 예약 발행 시나리오.

    Options
    -------
    - MetaOption: schedule_mode="random_window", schedule_at=지금+3시간, jitter=30분
                  → 실제 예약 시각은 [+2h30m, +3h30m] 범위 내 랜덤 결정.
    - 스팸 탐지 우회 목적: 여러 계정이 동일 시각에 발행되는 패턴을 방지.
    - dry_run=True이므로 실제 발행 없음.
    - post_images fixture 불필요.
    """
    from datetime import datetime, timedelta
    from automator.options import KST

    center = datetime.now(tz=KST).replace(second=0, microsecond=0) \
             + timedelta(hours=3)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+학습형태+과목+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            layout=["Paragraph 1", "Paragraph 2"],
            paragraph_prompt=(
                "노원구 수학 과외를 홍보하는 블로그 글을 작성해주세요. "
                "중등 수학 기초 다지기와 고등 수학 선행 학습을 강조해주세요."
            ),
        ))
        .with_meta(MetaOption(
            schedule_mode="random_window",
            schedule_at=center,
            schedule_jitter_minutes=30,
        ))
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True






# ---------------------------------------------------------------------------
# Diagnostic: ParagraphGenerator — Gemini API 실제 호출 확인
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_paragraph_generator_diagnostic():
    """
    Gemini API 실제 호출 단계별 진단 테스트.

    확인 항목:
      1. GEMINI_API_KEY 환경변수 로드 여부
      2. ParagraphGenerator 생성 (API 키 유효성)
      3. 실제 API 호출 및 응답 수신
      4. JSON 파싱 결과
      5. 단락 텍스트 내용

    Run:
        pytest tests/test_blog_e2e.py::test_paragraph_generator_diagnostic -m e2e -s -v
    """
    import os
    from automator.paragraph_generator import ParagraphGenerator

    print("\n========== PARAGRAPH GENERATOR DIAGNOSTIC ==========")

    # 1. API 키 확인
    api_key = os.getenv("GEMINI_API_KEY", "")
    print(f"  [1] GEMINI_API_KEY: {'✅ 설정됨 (' + api_key[:6] + '...)' if api_key else '❌ 미설정'}")
    assert api_key, "GEMINI_API_KEY가 .env에 설정되어 있지 않습니다."

    # 2. 생성
    try:
        gen = ParagraphGenerator(
            prompt="대치동 수학 과외를 홍보하는 학부모 대상 블로그 글",
            api_key=api_key,
        )
        print("  [2] ParagraphGenerator 생성: ✅")
    except Exception as e:
        print(f"  [2] ParagraphGenerator 생성 실패: ❌ {e}")
        raise

    # 3. 원본 API 응답 확인
    try:
        raw = gen._call_api(count=2)
        print(f"  [3] API 원본 응답:")
        print(f"      {raw[:300]!r}")
    except Exception as e:
        print(f"  [3] API 호출 실패: ❌ {e}")
        raise

    # 4. 파싱 결과 확인
    try:
        parsed = gen._parse(raw, count=2)
        print(f"  [4] 파싱 결과: ✅ {len(parsed)}개")
        for i, p in enumerate(parsed, 1):
            print(f"      단락 {i} ({len(p)}자): {p[:80]}...")
    except Exception as e:
        print(f"  [4] 파싱 실패: ❌ {e}")
        raise

    # 5. generate() 통합 호출
    result = gen.generate(count=3)
    print(f"  [5] generate(3) 결과: {len(result)}개")
    for i, p in enumerate(result, 1):
        print(f"      단락 {i} ({len(p)}자): {p[:80]}")
        assert len(p) > 10, f"단락 {i}가 너무 짧습니다: {p!r}"

    print("=====================================================\n")


# ===========================================================================
# Diagnostic: overlay, upload, representative image 단계별 진단
# ===========================================================================