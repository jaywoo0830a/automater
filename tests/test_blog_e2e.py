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
def test_two_placeholder_spans_exist(page: Page, account: AccountOption):
    page.goto(account.write_url)
    frame = page.frame_locator(_MAIN_FRAME)
    frame.locator(_EDITOR_BODY).wait_for(state="visible", timeout=15_000)
    assert frame.locator("span.se-placeholder.__se_placeholder").count() >= 2


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page, account: AccountOption):
    page.goto(account.write_url)
    frame = page.frame_locator(_MAIN_FRAME)
    frame.locator(_EDITOR_BODY).wait_for(state="visible", timeout=15_000)
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

    frame = page.frame_locator(_MAIN_FRAME).first

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


# ===========================================================================
# Diagnostic: overlay, upload, representative image 단계별 진단
# ===========================================================================

@pytest.mark.e2e
def test_diag_overlay_dismissal(page: Page, account: AccountOption):
    """
    오버레이(초안 복구, 도움말) 처리 진단.

    확인 항목:
      1. 에디터 로딩 완료 여부
      2. 초안 복구 팝업 존재 여부 및 selector 유효성
      3. 도움말 패널 존재 여부 및 selector 유효성
      4. SmartEditorOne.open() 이후 오버레이가 사라졌는지
    """
    print("\n\n========== DIAG: overlay_dismissal ==========")
    sel   = _EDITOR_SEL
    frame = page.frame_locator(_MAIN_FRAME).first

    # 1. raw 페이지 로드
    page.goto(account.write_url)
    page.wait_for_load_state("domcontentloaded")
    print(f"  [1] URL: {page.url[:80]}")

    # 2. 에디터 본문 대기
    try:
        frame.locator(_EDITOR_BODY).wait_for(state="visible", timeout=15_000)
        print("  [2] 에디터 로딩: ✅")
    except Exception as e:
        print(f"  [2] 에디터 로딩 실패: ❌ {e}")
        return

    import time; time.sleep(1)  # 오버레이 animate-in 대기

    # 3. 초안 복구 팝업
    draft_css   = sel.css("overlay_draft_cancel")
    draft_count = frame.locator(draft_css).count()
    print(f"  [3] 초안 복구 팝업 ({draft_css!r}): count={draft_count}")
    if draft_count:
        is_vis = frame.locator(draft_css).first.is_visible()
        print(f"      visible={is_vis}")

    # 4. 도움말 패널
    help_css   = sel.css("overlay_help_close")
    help_count = frame.locator(help_css).count()
    print(f"  [4] 도움말 닫기 버튼 ({help_css!r}): count={help_count}")
    if help_count:
        is_vis = frame.locator(help_css).first.is_visible()
        print(f"      visible={is_vis}")

    # 5. SmartEditorOne.open() 실행
    editor = SmartEditorOne(page, account.write_url)
    editor.open()
    print("  [5] SmartEditorOne.open() 완료")

    # open()이 page.goto()를 다시 실행하므로 frame을 새로 잡아야 함
    frame = page.frame_locator(_MAIN_FRAME).first

    # 6. open() 이후 오버레이 잔존 여부
    after_draft = frame.locator(draft_css).count()
    after_help  = frame.locator(help_css).count()
    print(f"  [6] open() 후 초안 팝업 count={after_draft}  도움말 count={after_help}")
    if after_draft:
        print(f"      ⚠️  초안 팝업이 아직 DOM에 있음 — visible={frame.locator(draft_css).first.is_visible()}")
    if after_help:
        print(f"      ⚠️  도움말 버튼이 아직 DOM에 있음 — visible={frame.locator(help_css).first.is_visible()}")

    print("=============================================\n")


@pytest.mark.e2e
def test_diag_upload_sequence(page: Page, account: AccountOption):
    """
    이미지 3장 연속 업로드 단계별 진단.

    확인 항목:
      1. 업로드 전 이미지 count
      2. 업로드 후 이미지 count (매 업로드마다)
      3. 라이브러리 패널 open/close 여부
      4. toolbar_image selector 업로드 후에도 유효한지
      5. editor_image_block count vs editor_image count 일치 여부
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"이미지 없음: {IMAGE_PATH!r}")

    print("\n\n========== DIAG: upload_sequence ==========")
    sel   = _EDITOR_SEL
    frame = page.frame_locator(_MAIN_FRAME).first

    editor = SmartEditorOne(page, account.write_url)
    editor.open()
    print("  open() 완료")

    img_css   = sel.css("editor_image")
    block_css = sel.css("editor_image_block")
    lib_css   = sel.css("library_close")
    trig_css  = sel.css("toolbar_image")

    for i in range(3):
        before_img   = frame.locator(img_css).count()
        before_block = frame.locator(block_css).count()
        print(f"\n  --- 업로드 {i+1} ---")
        print(f"  before: editor_image={before_img}  editor_image_block={before_block}")

        if i > 0:
            editor.move_cursor_to_end()

        # 라이브러리 패널이 현재 열려있나?
        lib_before = frame.locator(lib_css).count()
        print(f"  라이브러리 패널 (before): count={lib_before}, visible={frame.locator(lib_css).first.is_visible() if lib_before else False}")

        # toolbar_image 유효?
        trig_count = frame.locator(trig_css).count()
        print(f"  toolbar_image ({trig_css!r}): count={trig_count}")

        try:
            editor.upload_image(IMAGE_PATH)
            after_img   = frame.locator(img_css).count()
            after_block = frame.locator(block_css).count()
            lib_after   = frame.locator(lib_css).count()
            print(f"  after:  editor_image={after_img}  editor_image_block={after_block}")
            print(f"  라이브러리 패널 (after): count={lib_after}")
            if after_img == before_img:
                print(f"  ❌ 이미지가 증가하지 않았음! (before={before_img}, after={after_img})")
            else:
                print(f"  ✅ 이미지 추가됨 ({before_img} → {after_img})")
        except Exception as e:
            print(f"  ❌ upload_image 실패: {e}")

    # 최종 상태
    total_img   = frame.locator(img_css).count()
    total_block = frame.locator(block_css).count()
    total_rep   = frame.locator(sel.css("editor_image_rep")).count()
    print(f"\n  최종 editor_image={total_img}  editor_image_block={total_block}  editor_image_rep={total_rep}")
    if total_img != total_block:
        print(f"  ⚠️  img count({total_img}) ≠ block count({total_block}) — nth 기준이 다름!")

    print("=============================================\n")


@pytest.mark.e2e
def test_diag_representative_image(page: Page, account: AccountOption):
    """
    대표이미지 JS dispatchEvent 진단.

    확인 항목:
      1. rep 버튼 count (hover 없이)
      2. rep 버튼의 class/visibility 상태
      3. JS dispatchEvent 실행 전/후 se-is-selected 변화
      4. 0번, 1번, 2번 각각 시도
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"이미지 없음: {IMAGE_PATH!r}")

    print("\n\n========== DIAG: representative_image ==========")
    sel   = _EDITOR_SEL
    frame = page.frame_locator(_MAIN_FRAME).first

    editor = SmartEditorOne(page, account.write_url)
    editor.open()

    # 이미지 3장 업로드
    for i in range(3):
        if i > 0: editor.move_cursor_to_end()
        editor.upload_image(IMAGE_PATH)
    import time; time.sleep(1)

    rep_css     = sel.css("editor_image_rep")
    rep_sel_css = sel.css("editor_image_rep_selected")
    js_frame    = next((f for f in page.frames if f != page.main_frame), page.main_frame)

    rep_count = frame.locator(rep_css).count()
    print(f"  rep 버튼 count (hover 없이): {rep_count}")

    if rep_count == 0:
        print("  ❌ rep 버튼이 DOM에 없음!")
        # DOM 직접 탐색
        found = js_frame.evaluate("""() => {
            const btns = document.querySelectorAll('button');
            return [...btns].filter(b => b.className.includes('rep') || b.innerText.includes('대표'))
                            .map(b => ({cls: b.className, text: b.innerText.trim().slice(0,20)}));
        }""")
        print(f"  'rep' 또는 '대표' 포함 버튼: {found}")
        return

    # 각 버튼 상태
    for i in range(rep_count):
        cls = frame.locator(rep_css).nth(i).get_attribute("class") or ""
        vis = frame.locator(rep_css).nth(i).is_visible()
        print(f"  rep[{i}] visible={vis}  class={cls[:60]}")

    # JS dispatchEvent 각 인덱스 시도
    for idx in range(min(rep_count, 3)):
        result = js_frame.evaluate(
            """([css, idx]) => {
                const btns = document.querySelectorAll(css);
                if (idx >= btns.length) return `out of range (${btns.length})`;
                btns[idx].dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                return btns[idx].classList.contains('se-is-selected') ? 'selected' : 'not-selected';
            }""",
            [rep_css, idx],
        )
        sel_count = frame.locator(rep_sel_css).count()
        print(f"  dispatchEvent({idx}) → {result!r}  selected_count={sel_count}")
        time.sleep(0.3)

    print("=============================================\n")


# ===========================================================================
# Diagnostic: set_representative_image 단계별 진단
# ===========================================================================

@pytest.mark.e2e
def test_diag_representative_image_indexing(page: Page, account: AccountOption):
    """
    대표이미지 설정 index 불일치 진단.

    확인 항목:
      1. 이미지 3장 업로드 후 DOM 상태
      2. editor_image_block count vs editor_image_rep button count
      3. 각 rep 버튼의 DOM 위치 (어느 이미지 컴포넌트 안에 있는지)
      4. index 0, 1, 2 각각에 대해 JS dispatchEvent 결과
      5. se-is-selected 상태가 실제로 바뀌는지

    Run:
        pytest tests/test_blog_e2e.py::test_diag_representative_image_indexing -m e2e -s -v
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"이미지 없음: {IMAGE_PATH!r}")

    import time

    print("\n\n========== DIAG: rep image indexing ==========")

    sel      = _EDITOR_SEL
    frame    = page.frame_locator(_MAIN_FRAME).first
    editor   = SmartEditorOne(page, account.write_url)
    js_frame = next((f for f in page.frames if f != page.main_frame), page.main_frame)

    editor.open()
    for i in range(3):
        if i > 0:
            editor.move_cursor_to_end()
        editor.upload_image(IMAGE_PATH)
    time.sleep(1)

    block_css   = sel.css("editor_image_block")
    rep_css     = sel.css("editor_image_rep")
    rep_sel_css = sel.css("editor_image_rep_selected")

    # 1. DOM 상태
    n_blocks = frame.locator(block_css).count()
    n_rep    = frame.locator(rep_css).count()
    n_imgs   = frame.locator(sel.css("editor_image")).count()
    print(f"  [1] editor_image={n_imgs}  image_block={n_blocks}  rep_btn={n_rep}")

    if n_blocks != n_rep:
        print(f"  ⚠️  block count({n_blocks}) ≠ rep_btn count({n_rep})")
        print(f"       → nth index가 block과 rep_btn 사이에서 어긋남!")

    # 2. 각 rep 버튼의 class 및 위치
    print(f"  [2] rep 버튼 개별 상태:")
    all_rep_info = js_frame.evaluate(f"""() => {{
        const btns = document.querySelectorAll('{rep_css}');
        return [...btns].map((btn, i) => {{
            const block = btn.closest('{block_css}');
            const blockIdx = block
                ? [...document.querySelectorAll('{block_css}')].indexOf(block)
                : -1;
            return {{
                btnIdx:   i,
                blockIdx: blockIdx,
                cls:      btn.className,
                visible:  btn.offsetParent !== null,
            }};
        }});
    }}""")
    for info in all_rep_info:
        sel_mark = "✅" if "se-is-selected" in info["cls"] else "  "
        print(f"       btn[{info['btnIdx']}] → block[{info['blockIdx']}]  "
              f"visible={info['visible']}  {sel_mark} {info['cls'][:50]}")

    # 3. dispatchEvent 테스트: index 0, 1, 2 순서대로
    print(f"  [3] dispatchEvent 테스트:")
    for target_idx in range(min(n_rep, 3)):
        # 현재 선택 상태 초기화 (다른 걸 먼저 선택)
        other = (target_idx + 1) % n_rep
        js_frame.evaluate(
            f"""([css, i]) => {{
                const btns = document.querySelectorAll(css);
                if (btns[i]) btns[i].dispatchEvent(
                    new MouseEvent('click', {{bubbles:true, cancelable:true}})
                );
            }}""",
            [rep_css, other],
        )
        time.sleep(0.3)

        # 타겟 클릭
        result = js_frame.evaluate(
            f"""([css, i]) => {{
                const btns = document.querySelectorAll(css);
                if (i >= btns.length) return 'out of range';
                btns[i].dispatchEvent(
                    new MouseEvent('click', {{bubbles:true, cancelable:true}})
                );
                return {{
                    clicked_idx:   i,
                    is_selected:   btns[i].classList.contains('se-is-selected'),
                    selected_idxs: [...btns].map((b,j) => b.classList.contains('se-is-selected') ? j : -1)
                                           .filter(j => j >= 0),
                }};
            }}""",
            [rep_css, target_idx],
        )
        time.sleep(0.3)

        if isinstance(result, dict):
            ok = "✅" if (result["is_selected"] and result["selected_idxs"] == [target_idx]) else "❌"
            print(f"       {ok} target={target_idx}  is_selected={result['is_selected']}  "
                  f"selected_idxs={result['selected_idxs']}")
            if result["selected_idxs"] != [target_idx]:
                print(f"          ⚠️  예상: [{target_idx}]  실제: {result['selected_idxs']}")
        else:
            print(f"       ❌ target={target_idx}  result={result!r}")

    # 4. SmartEditorOne.set_representative_image() 직접 테스트
    print(f"  [4] SmartEditorOne.set_representative_image() 테스트:")
    for idx in range(min(n_blocks, 3)):
        try:
            editor.set_representative_image(idx)
            time.sleep(0.3)
            # 어느 버튼이 선택됐나
            selected = js_frame.evaluate(
                f"""(css) => {{
                    const btns = document.querySelectorAll(css);
                    return [...btns].map((b,i) => b.classList.contains('se-is-selected') ? i : -1)
                                   .filter(i => i >= 0);
                }}""",
                rep_css,
            )
            ok = "✅" if selected == [idx] else "❌"
            print(f"       {ok} set_representative_image({idx}) → selected={selected}")
        except Exception as e:
            print(f"       ❌ set_representative_image({idx}) 예외: {e}")

    print("==============================================\n")


@pytest.mark.e2e
def test_diag_shadow_dom_and_nested_frames(page: Page, account: AccountOption):
    """
    rep 버튼이 shadow DOM 또는 중첩 iframe 안에 있는지 확인.

    Playwright locator는 shadow DOM을 자동 통과하지만
    querySelectorAll은 통과하지 못함 → dispatchEvent 대안 필요.

    Run:
        pytest tests/test_blog_e2e.py::test_diag_shadow_dom_and_nested_frames -m e2e -s -v
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"이미지 없음: {IMAGE_PATH!r}")

    import time

    print("\n\n========== DIAG: shadow DOM & nested frames ==========")

    sel    = _EDITOR_SEL
    editor = SmartEditorOne(page, account.write_url)
    editor.open()
    editor.upload_image(IMAGE_PATH)
    time.sleep(1)

    rep_css = sel.css("editor_image_rep")

    # 1. page.frames 전체 (중첩 포함)
    print(f"  [1] 전체 frame 목록 ({len(page.frames)}개):")
    for i, f in enumerate(page.frames):
        try:
            count = f.evaluate(
                f"() => document.querySelectorAll('{rep_css}').length"
            )
        except Exception:
            count = "N/A"
        print(f"    [{i}] rep={count}  url={f.url[:65]!r}")

    # 2. shadow DOM 탐색
    print(f"\n  [2] shadow DOM 탐색:")
    post_frame = next(
        (f for f in page.frames if "PostWriteForm" in f.url), None
    )
    if post_frame:
        shadow_result = post_frame.evaluate(f"""() => {{
            // shadow DOM 재귀 탐색
            function queryAll(root, selector) {{
                const results = [...root.querySelectorAll(selector)];
                root.querySelectorAll('*').forEach(el => {{
                    if (el.shadowRoot) {{
                        results.push(...queryAll(el.shadowRoot, selector));
                    }}
                }});
                return results;
            }}
            const btns = queryAll(document, '{rep_css}');
            return btns.map(b => ({{
                cls:      b.className,
                inShadow: b.getRootNode() !== document,
                host:     b.getRootNode().host
                          ? b.getRootNode().host.tagName : 'none',
            }}));
        }}""")
        print(f"    shadow DOM 탐색 결과: {len(shadow_result)}개")
        for info in shadow_result:
            print(f"      inShadow={info['inShadow']}  host={info['host']}  cls={info['cls'][:50]}")
    else:
        print("    PostWriteForm frame 없음")

    # 3. Playwright evaluate (frame locator 경유)
    print(f"\n  [3] Playwright frame.evaluate (FrameLocator 경유):")
    frame = page.frame_locator(_MAIN_FRAME).first
    try:
        # FrameLocator는 evaluate 미지원 — Frames를 통해 접근
        result = page.frames[1].evaluate(f"""() => {{
            const btns = document.querySelectorAll('{rep_css}');
            return {{
                direct: btns.length,
                allButtons: [...document.querySelectorAll('button')]
                    .filter(b => b.className.includes('rep') || b.className.includes('image'))
                    .map(b => b.className).slice(0, 5),
            }};
        }}""")
        print(f"    direct querySelectorAll: {result['direct']}")
        print(f"    관련 button classes: {result['allButtons']}")
    except Exception as e:
        print(f"    ❌ {e}")

    # 4. Playwright locator evaluate (pierce shadow DOM)
    print(f"\n  [4] Playwright locator.evaluate (shadow DOM 통과):")
    try:
        rep_loc = frame.locator(rep_css).first
        cls = rep_loc.evaluate("el => el.className")
        print(f"    ✅ locator.evaluate 성공: cls={cls[:60]}")
        # dispatchEvent via locator.evaluate
        result = rep_loc.evaluate("""el => {
            el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
            return el.classList.contains('se-is-selected') ? 'selected' : 'not-selected';
        }""")
        print(f"    dispatchEvent via locator.evaluate: {result!r}")
    except Exception as e:
        print(f"    ❌ {e}")

    print("======================================================\n")


@pytest.mark.e2e
def test_diag_rep_button_hover_behavior(page: Page, account: AccountOption):
    """
    hover 전후로 대표 버튼이 DOM에 나타나는지 확인.

    확인 항목:
      1. hover 전: button.se-set-rep-image-button DOM 존재 여부
      2. image_block hover 후: 버튼 DOM 등장 여부
      3. hover 후 Playwright locator.click() 가능 여부
      4. hover 후 locator.evaluate → dispatchEvent 가능 여부

    Run:
        pytest tests/test_blog_e2e.py::test_diag_rep_button_hover_behavior -m e2e -s -v
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"이미지 없음: {IMAGE_PATH!r}")

    import time

    print("\n\n========== DIAG: rep button hover behavior ==========")

    sel      = _EDITOR_SEL
    frame    = page.frame_locator(_MAIN_FRAME).first
    editor   = SmartEditorOne(page, account.write_url)
    js_frame = next((f for f in page.frames if "PostWriteForm" in f.url), page.main_frame)

    editor.open()
    editor.upload_image(IMAGE_PATH)
    time.sleep(1)

    rep_css   = sel.css("editor_image_rep")
    block_css = sel.css("editor_image_block")

    # 1. hover 전 상태
    before_count = js_frame.evaluate(
        f"() => document.querySelectorAll('{rep_css}').length"
    )
    before_visible = frame.locator(rep_css).count()
    print(f"  [1] hover 전:")
    print(f"      querySelectorAll count = {before_count}")
    print(f"      Playwright locator count = {before_visible}")

    # 2. image_block hover
    block = frame.locator(block_css).first
    try:
        block.hover()
        time.sleep(0.5)
        print(f"  [2] image_block hover: ✅")
    except Exception as e:
        print(f"  [2] image_block hover: ❌ {e}")

    # 3. hover 후 querySelectorAll
    after_count = js_frame.evaluate(
        f"() => document.querySelectorAll('{rep_css}').length"
    )
    after_visible = frame.locator(rep_css).count()
    print(f"  [3] hover 후:")
    print(f"      querySelectorAll count = {after_count}")
    print(f"      Playwright locator count = {after_visible}")

    if after_count > 0:
        print(f"      → hover 후 querySelectorAll 작동 ✅ dispatchEvent 사용 가능")
    else:
        print(f"      → hover 후에도 querySelectorAll 안 됨 → locator.evaluate 사용 필요")

    # 4. locator.evaluate로 dispatchEvent 시도
    print(f"  [4] locator.evaluate → dispatchEvent:")
    try:
        result = frame.locator(rep_css).first.evaluate("""el => {
            el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
            return el.classList.contains('se-is-selected') ? 'selected' : 'not-selected';
        }""")
        print(f"      결과: {result!r}")
    except Exception as e:
        print(f"      ❌ {e}")

    # 5. Playwright locator.click() 직접 시도
    print(f"  [5] Playwright locator.click() 직접:")
    try:
        frame.locator(rep_css).first.click(force=True)
        time.sleep(0.3)
        selected = js_frame.evaluate(
            f"() => document.querySelectorAll('{sel.css('editor_image_rep_selected')}').length"
        )
        print(f"      click 성공, selected count = {selected}")
    except Exception as e:
        print(f"      ❌ {e}")

    print("=====================================================\n")
