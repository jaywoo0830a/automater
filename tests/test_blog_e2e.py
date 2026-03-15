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


def _run_job(job, editor) -> None:
    """
    Run a NaverBlogJob and assert success.

    ParagraphGenerator is always mocked with UDHR stub paragraphs in pipeline tests
    (see conftest.py) — no real Gemini API calls are made here.
    """
    ok = job.run(editor)
    assert ok is True, "job.run() returned False — 브라우저/에디터 오류 확인 필요" 


# ---------------------------------------------------------------------------
# Pipeline: 브라우저 자동화 전체 흐름 검증
#
# 각 테스트는 서로 다른 핵심 경로를 커버한다.
# 제목 옵션 변형(template, learning_type, fixed_title)은 test_title_unit.py에서 커버.
#
#   full_layout  — 이미지+썸네일+단락 업로드 전체 흐름  (이미지 필요)
#   text_only    — 이미지 없이 단락만                    (이미지 불필요)
#   minimal      — 빈 레이아웃 → 단락 1개 자동 생성     (이미지 불필요)
#   scheduled    — 예약 발행 UI 설정 흐름               (이미지 불필요)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_full_layout(
    editor: SmartEditorOne,
    account: AccountOption,
    post_images: tuple,
):
    """
    이미지 업로드 + 썸네일 + 단락이 섞인 전체 레이아웃 흐름.
    Image×3 → Paragraph 1 → Thumbnail → Paragraph 2, 3
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
            paragraph_prompt="대치동 수학 과외를 홍보하는 학부모 대상 블로그 글.",
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_text_only(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    이미지 없이 단락만 있는 흐름.
    이미지 fixture 없이도 실행 가능.
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
            layout=["Paragraph 1", "Paragraph 2", "Paragraph 3"],
            paragraph_prompt="송파구 국어 과외를 홍보하는 블로그 글.",
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_minimal(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    빈 레이아웃 — open → write_title → publish 최소 경로.
    """
    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="테스트 포스트"))
        .with_content(ContentOption())
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_scheduled(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    예약 발행(fixed) 전체 잡 흐름.
    시/분 select 설정 후 dry_run으로 종료.
    """
    from datetime import datetime, timedelta
    from automator.options import KST

    now    = datetime.now(tz=KST)
    target = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0) + timedelta(hours=2)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="예약 발행 테스트"))
        .with_content(ContentOption(layout=["Paragraph 1"]))
        .with_meta(MetaOption(
            schedule_mode="fixed",
            schedule_at=target,
        ))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


# ===========================================================================
# Diagnostic: overlay, upload, representative image 단계별 진단
# ===========================================================================