"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.

Tests run against a real browser. Requires either:
  1. A valid session_state.json (preferred — skips login), OR
  2. NAVER_ID / NAVER_PW in .env

Run all e2e tests:
    pytest tests/test_blog_e2e.py -m e2e -v

Run only the publish test (writes a real post):
    pytest tests/test_blog_e2e.py::test_full_post_sequence -m "e2e and slow" -v
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from automator.config import settings
from automator.browser import (
    MAIN_FRAME,
    EDITOR_CONTENT,
    UPLOADED_IMAGE,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
)
from automator.editor import PostContent
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob
from automator.selector_loader import SelectorLoader

load_dotenv()

SESSION_PATH     = os.getenv("SESSION_PATH", "session_state.json")
NAVER_ID         = os.getenv("NAVER_ID", "")
NAVER_PW         = os.getenv("NAVER_PW", "")
LOGIN_JSON_PATH  = os.getenv("LOGIN_JSON_PATH",  "selectors/naver/login.json")
EDITOR_JSON_PATH = os.getenv("EDITOR_JSON_PATH", "selectors/naver/editor.json")
IMAGE_PATH       = os.getenv("TEST_IMAGE_PATH", "smile.jpg")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_instance():
    """Single Chromium browser for the whole test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser):
    """
    Authenticated BrowserContext.
    Prefers session_state.json; falls back to env-var login.
    """
    if os.path.exists(SESSION_PATH):
        ctx = browser_instance.new_context(storage_state=SESSION_PATH)
    elif NAVER_ID and NAVER_PW:
        ctx  = browser_instance.new_context()
        page = ctx.new_page()
        sel  = SelectorLoader.load(LOGIN_JSON_PATH)
        page.goto("https://nid.naver.com/nidlogin.login")
        sel.locator(page, "naver_login_id").fill(NAVER_ID)
        sel.locator(page, "naver_login_pw").fill(NAVER_PW)
        sel.locator(page, "naver_login_submit").click()
        page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
        ctx.storage_state(path=SESSION_PATH)
        page.close()
    else:
        pytest.skip("No session file or credentials. Set NAVER_ID/NAVER_PW in .env.")

    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext):
    """Fresh page per test."""
    p = auth_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor(page: Page) -> SmartEditorOne:
    """SmartEditorOne bound to the authenticated page."""
    return SmartEditorOne(page, settings.write_url, EDITOR_JSON_PATH)


# ---------------------------------------------------------------------------
# E2E: Editor loads correctly
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page):
    """Smart Editor iframe renders after navigating to the write page."""
    page.goto(settings.write_url)
    page.frame_locator(MAIN_FRAME) \
        .locator(EDITOR_CONTENT) \
        .wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
def test_two_placeholder_spans_exist(page: Page):
    """At least 2 se-placeholder spans exist (title + body)."""
    page.goto(settings.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    count = frame.locator("span.se-placeholder.__se_placeholder").count()
    assert count >= 2, f"Expected >= 2 placeholder spans, found {count}"


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page):
    """Placeholder parent IDs follow the SE-{uuid} pattern."""
    page.goto(settings.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    parent_id = (
        frame.locator("span.se-placeholder.__se_placeholder")
             .nth(0)
             .locator("..")
             .get_attribute("id")
    )
    assert parent_id and parent_id.startswith("SE-"), (
        f"Expected id to start with 'SE-', got: {parent_id!r}"
    )


# ---------------------------------------------------------------------------
# E2E: Image upload
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(editor: SmartEditorOne, page: Page):
    """Uploading an image results in a visible image block in the editor."""
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    editor.open()
    editor.upload_image(IMAGE_PATH)

    frame = page.frame_locator(MAIN_FRAME).first
    assert frame.locator(UPLOADED_IMAGE).first.is_visible()


# ---------------------------------------------------------------------------
# E2E: Representative image
# ---------------------------------------------------------------------------

def _upload_three_images(editor: SmartEditorOne, page: Page) -> None:
    """Upload 3 copies of IMAGE_PATH, moving cursor between each."""
    editor.open()
    editor.upload_image(IMAGE_PATH)
    editor.move_cursor_to_end()
    editor.upload_image(IMAGE_PATH)
    editor.move_cursor_to_end()
    editor.upload_image(IMAGE_PATH)

    frame = page.frame_locator(MAIN_FRAME).first
    frame.locator(UPLOADED_IMAGE).nth(2).wait_for(state="visible", timeout=15_000)
    count = frame.locator(REP_IMAGE_BUTTON).count()
    assert count == 3, f"Expected 3 rep buttons after 3 uploads, got {count}"


def _assert_only_nth_selected(page: Page, index: int, total: int) -> None:
    frame    = page.frame_locator(MAIN_FRAME).first
    selected = frame.locator(REP_IMAGE_BUTTON_SELECTED)
    buttons  = frame.locator(REP_IMAGE_BUTTON)

    assert selected.count() == 1
    for i in range(total):
        classes = buttons.nth(i).get_attribute("class") or ""
        if i == index:
            assert "se-is-selected" in classes
        else:
            assert "se-is-selected" not in classes


@pytest.mark.e2e
def test_set_first_image_as_representative(editor: SmartEditorOne, page: Page):
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")
    _upload_three_images(editor, page)
    editor.set_representative_image(0)
    _assert_only_nth_selected(page, 0, 3)


@pytest.mark.e2e
def test_set_second_image_as_representative(editor: SmartEditorOne, page: Page):
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")
    _upload_three_images(editor, page)
    editor.set_representative_image(1)
    _assert_only_nth_selected(page, 1, 3)


@pytest.mark.e2e
def test_set_third_image_as_representative(editor: SmartEditorOne, page: Page):
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")
    _upload_three_images(editor, page)
    editor.set_representative_image(2)
    _assert_only_nth_selected(page, 2, 3)


# ---------------------------------------------------------------------------
# E2E: Full job run via NaverBlogJob
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_full_post_sequence(editor: SmartEditorOne):
    """
    NaverBlogJob.run() publishes a real post end-to-end.
    WARNING: This writes a live post. Delete it afterward.

    Run with:
        pytest tests/test_blog_e2e.py::test_full_post_sequence -m "e2e and slow"
    """
    content = PostContent(
        title="[자동화 테스트] Playwright로 작성한 포스트",
        body=(
            "안녕하세요! 이 글은 Playwright 자동화 테스트로 작성된 포스트입니다.\n\n"
            "테스트 완료 후 삭제 예정입니다."
        ),
    )
    job = NaverBlogJob(editor)
    assert job.run(content) is True


@pytest.mark.e2e
@pytest.mark.slow
def test_title_and_body_visible_before_publish(editor: SmartEditorOne, page: Page):
    """Fills title and body, verifies publish trigger is visible — does NOT confirm."""
    editor.open()
    editor.write_title("[자동화 테스트] 발행 안 함")
    editor.write_body("발행하지 않는 테스트입니다.")

    sel = SelectorLoader.load(EDITOR_JSON_PATH)
    el  = sel.locator(page, "publish_trigger")
    el.wait_for(state="visible", timeout=5_000)
    assert el.is_visible()
