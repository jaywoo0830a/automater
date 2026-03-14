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
from automator.browser import (
    MAIN_FRAME, EDITOR_CONTENT, UPLOADED_IMAGE,
    REP_IMAGE_BUTTON, REP_IMAGE_BUTTON_SELECTED,
    NaverLoginLocators,
)
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
        NaverLoginLocators.id_field(page).fill(account.naver_id)
        NaverLoginLocators.pw_field(page).fill(account.naver_pw)
        NaverLoginLocators.submit_button(page).click()
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


# ---------------------------------------------------------------------------
# E2E: Editor loads
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page, account: AccountOption):
    page.goto(account.write_url)
    page.frame_locator(MAIN_FRAME) \
        .locator(EDITOR_CONTENT) \
        .wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
def test_two_placeholder_spans_exist(page: Page, account: AccountOption):
    page.goto(account.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    assert frame.locator("span.se-placeholder.__se_placeholder").count() >= 2


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page, account: AccountOption):
    page.goto(account.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    parent_id = (
        frame.locator("span.se-placeholder.__se_placeholder")
             .nth(0).locator("..").get_attribute("id")
    )
    assert parent_id and parent_id.startswith("SE-")


# ---------------------------------------------------------------------------
# E2E: Image upload
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(editor: SmartEditorOne, page: Page):
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")
    editor.open()
    editor.upload_image(IMAGE_PATH)
    assert page.frame_locator(MAIN_FRAME).first.locator(UPLOADED_IMAGE).first.is_visible()


# ---------------------------------------------------------------------------
# E2E: Representative image
# ---------------------------------------------------------------------------

def _upload_three(editor, page):
    editor.open()
    for i in range(3):
        if i > 0: editor.move_cursor_to_end()
        editor.upload_image(IMAGE_PATH)
    page.frame_locator(MAIN_FRAME).first \
        .locator(UPLOADED_IMAGE).nth(2) \
        .wait_for(state="visible", timeout=15_000)
    assert page.frame_locator(MAIN_FRAME).first.locator(REP_IMAGE_BUTTON).count() == 3


def _assert_selected(page, index, total):
    frame   = page.frame_locator(MAIN_FRAME).first
    buttons = frame.locator(REP_IMAGE_BUTTON)
    assert frame.locator(REP_IMAGE_BUTTON_SELECTED).count() == 1
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


# ---------------------------------------------------------------------------
# Diagnostic: find the correct image trigger selector after an upload
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_image_trigger_selector_after_upload(page: Page, account: AccountOption):
    """
    Uploads one image, then probes every candidate selector for the
    image-add button and prints count + visibility.

    Run with -s to see output:
        pytest tests/test_blog_e2e.py::test_image_trigger_selector_after_upload -m e2e -s
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    local_editor = SmartEditorOne(page, account.write_url)
    local_editor.open()
    local_editor.upload_image(IMAGE_PATH)

    frame = page.frame_locator(MAIN_FRAME).first

    print("\n\n========== IMAGE TRIGGER DIAGNOSTIC ==========")

    # CSS selectors
    css_candidates = [
        "button[data-name='image']",
        "button[data-name='image'][data-group='documentToolbar']",
        ".se-image-toolbar-button",
        ".se-document-toolbar-basic-button[data-name='image']",
        "button.se-text-icon-toolbar-button[data-name='image']",
    ]
    for sel in css_candidates:
        try:
            count   = frame.locator(sel).count()
            visible = frame.locator(sel).first.is_visible() if count > 0 else False
            print(f"  locator({sel!r:60s}) count={count}  first_visible={visible}")
        except Exception as e:
            print(f"  locator({sel!r:60s}) ERROR: {e}")

    # get_by_role variants
    role_candidates = [
        ("사진",    {}),
        ("사진 추가", {}),
        ("사진 추가", {"exact": True}),
        ("사진 교체", {}),
    ]
    for name, kw in role_candidates:
        kw_str = f", {kw}" if kw else ""
        try:
            loc     = frame.get_by_role("button", name=name, **kw)
            count   = loc.count()
            visible = loc.first.is_visible() if count > 0 else False
            print(f"  get_by_role('button', name={name!r}{kw_str:20s}) count={count}  first_visible={visible}")
        except Exception as e:
            print(f"  get_by_role('button', name={name!r}{kw_str:20s}) ERROR: {e}")

    print("==============================================\n")


# ---------------------------------------------------------------------------
# E2E: Full job (publishes a live post — delete afterward)
#
# Scenario: "대치동 수학 과외" 를 검색하는 학부모 타겟 포스팅
#   - TitleOption: 프리셋 랜덤 생성 (지역+과목+학습형태+솔트)
#   - ContentOption layout: Image 1 → Image 2 → Paragraph 1
#                           → Thumbnail 1 → Paragraph 2 → Paragraph 3
#   - 이미지: 환경변수 TEST_PREVIEW_1, TEST_PREVIEW_2, TEST_THUMBNAIL_1 로 주입
#             미설정 시 pytest.skip
# ---------------------------------------------------------------------------

@pytest.fixture
def post_images():
    """
    Resolve real image paths from environment variables.

    Set in .env:
        TEST_PREVIEW_1=images/preview_1.png
        TEST_PREVIEW_2=images/preview_2.png
        TEST_PREVIEW_3=images/preview_3.png
        TEST_THUMBNAIL_1=images/thumbnail_base_1.png

    Skips the test if any path is missing or the file does not exist.
    """
    paths = {
        "TEST_PREVIEW_1":   TEST_PREVIEW_1,
        "TEST_PREVIEW_2":   TEST_PREVIEW_2,
        "TEST_PREVIEW_3":   TEST_PREVIEW_3,
        "TEST_THUMBNAIL_1": TEST_THUMBNAIL_1,
    }
    for env_key, val in paths.items():
        if not val:
            pytest.skip(f"Set {env_key} in .env to run the publish test")
        if not os.path.exists(val):
            pytest.skip(f"{env_key}={val!r} — file not found")
    return TEST_PREVIEW_1, TEST_PREVIEW_2, TEST_PREVIEW_3, TEST_THUMBNAIL_1


@pytest.mark.e2e
@pytest.mark.slow
def test_full_post_sequence(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    Full end-to-end sequence test (DRY RUN — publish is skipped).

    Scenario — "대치동 수학 과외" 타겟 포스팅:
      - 제목: 프리셋 기반 랜덤 생성 (지역+과목+학습형태+솔트)
      - 레이아웃: Image 1 → Image 2 → Image 3 → Paragraph 1
                  → Thumbnail 1 → Paragraph 2 → Paragraph 3
      - 이미지: .env의 TEST_PREVIEW_1~3, TEST_THUMBNAIL_1

    publish()는 dry_run=True로 인해 실제 발행하지 않습니다.
    글쓰기 팝업은 수동으로 닫거나 그냥 두면 됩니다.

    Prerequisites:
        1. session_state.json (또는 NAVER_ID/PW) 유효
        2. .env에 TEST_PREVIEW_1, TEST_PREVIEW_2, TEST_PREVIEW_3, TEST_THUMBNAIL_1 설정
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
