"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.
Requires:
  1. A valid session_state.json
  OR
  2. NAVER_ID / NAVER_PW environment variables in .env

Run with:
    pytest tests/test_blog_e2e.py -m e2e -v
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from automator.config import settings
from automator import selectors
from automator.blog import (
    BlogPost,
    LOGIN_URL,
    session_exists,
    login,
    wait_for_editor,
    fill_title,
    fill_body,
    upload_image,
    set_representative_image,
    click_publish_trigger,
    click_publish_confirm,
    post_blog,
)

load_dotenv()

SESSION_PATH = os.getenv("SESSION_PATH", "session_state.json")
NAVER_ID     = os.getenv("NAVER_ID", "")
NAVER_PW     = os.getenv("NAVER_PW", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_instance():
    """Launch a single Chromium browser for the whole test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser):
    """
    Provide an authenticated BrowserContext.
    Prefers session_state.json; falls back to env-var login.
    Skips the entire session if neither is available.
    """
    if session_exists(SESSION_PATH):
        ctx = browser_instance.new_context(storage_state=SESSION_PATH)
    elif NAVER_ID and NAVER_PW:
        ctx = browser_instance.new_context()
        page = ctx.new_page()
        login(page, NAVER_ID, NAVER_PW)
        # Save session AFTER navigating to write_url so all cookies are set
        ctx.storage_state(path=SESSION_PATH)
        page.close()
    else:
        pytest.skip(
            "No session file or credentials found. "
            "Set NAVER_ID/NAVER_PW in .env."
        )

    yield ctx
    ctx.close()


@pytest.fixture()
def page(auth_context: BrowserContext):
    """Open a fresh page per test, then close it."""
    p = auth_context.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# E2E: Editor loads correctly
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page):
    """Test that the Smart Editor iframe renders after navigating to the write page."""
    page.goto(settings.write_url)
    page.frame_locator(selectors.MAIN_FRAME) \
        .locator(selectors.EDITOR_CONTENT) \
        .wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
def test_two_placeholder_spans_exist(page: Page):
    """
    Test that at least 2 se-placeholder spans exist in the editor.
    Validates the nth(0)/nth(1) fallback selector strategy.
    """
    page.goto(settings.write_url)
    frame = page.frame_locator(selectors.MAIN_FRAME)
    frame.locator(selectors.EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)

    count = frame.locator(selectors.PLACEHOLDER).count()
    assert count >= 2, f"Expected at least 2 placeholder spans, found {count}."


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page):
    """
    Confirm that placeholder parent IDs follow the SE-{uuid} pattern,
    validating why we must NOT hardcode them.
    """
    page.goto(settings.write_url)
    frame = page.frame_locator(selectors.MAIN_FRAME)
    frame.locator(selectors.EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)

    parent_id = frame.locator(selectors.PLACEHOLDER).nth(0).locator("..").get_attribute("id")
    assert parent_id is not None
    assert parent_id.startswith("SE-"), f"Expected id to start with 'SE-', got: {parent_id!r}"


# ---------------------------------------------------------------------------
# E2E: Image upload
# ---------------------------------------------------------------------------

IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "smile.jpg")


@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(page: Page):
    """
    Test that clicking the image trigger and selecting a file
    inserts a visible image element into the editor.
    Does NOT publish — safe to run repeatedly.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    wait_for_editor(page)
    upload_image(page, IMAGE_PATH)

    frame = page.frame_locator(selectors.MAIN_FRAME).first
    img = frame.locator(selectors.UPLOADED_IMAGE).first
    assert img.is_visible(), "Uploaded image should be visible in the editor"


# ---------------------------------------------------------------------------
# E2E: Representative (thumbnail) image
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_first_image_is_representative_by_default(page: Page):
    """
    Upload 2 images and verify the first one is automatically
    set as the representative (thumbnail) image.

    Fully automated — no manual intervention needed.
    Does NOT publish.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    wait_for_editor(page)

    # Upload two images
    upload_image(page, IMAGE_PATH)
    upload_image(page, IMAGE_PATH)

    frame = page.frame_locator(selectors.MAIN_FRAME).first

    # Wait for "대표" buttons to appear
    rep_buttons = frame.locator(selectors.REP_IMAGE_BUTTON)
    rep_buttons.first.wait_for(state="visible", timeout=10_000)
    assert rep_buttons.count() >= 2, (
        f"Expected 2+ rep buttons, found {rep_buttons.count()}"
    )

    # The first image should be representative by default
    selected = frame.locator(selectors.REP_IMAGE_BUTTON_SELECTED)
    assert selected.count() == 1, "Exactly one image should be representative"

    # Verify it's the first button that has the selected state
    first_classes = rep_buttons.nth(0).get_attribute("class") or ""
    assert "se-is-selected" in first_classes, (
        "First image should be representative by default"
    )


@pytest.mark.e2e
def test_set_last_image_as_representative(page: Page):
    """
    Upload 2 images, then set the last (second) image as the
    representative (thumbnail) image.

    Fully automated — no manual intervention needed.
    Does NOT publish.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    wait_for_editor(page)

    # Upload two images
    upload_image(page, IMAGE_PATH)
    upload_image(page, IMAGE_PATH)

    frame = page.frame_locator(selectors.MAIN_FRAME).first

    # Wait for "대표" buttons to appear
    rep_buttons = frame.locator(selectors.REP_IMAGE_BUTTON)
    rep_buttons.first.wait_for(state="visible", timeout=10_000)
    count = rep_buttons.count()
    assert count >= 2, f"Expected 2+ rep buttons, found {count}"

    # Set the last image as representative
    last_index = count - 1
    set_representative_image(page, index=last_index)

    # Verify exactly one image is representative
    selected = frame.locator(selectors.REP_IMAGE_BUTTON_SELECTED)
    assert selected.count() == 1, "Exactly one image should be representative"

    # Verify it's the last button that has the selected state
    last_classes = rep_buttons.nth(last_index).get_attribute("class") or ""
    assert "se-is-selected" in last_classes, (
        f"Last image (index={last_index}) should be representative"
    )

    # Verify the first button is NOT selected
    first_classes = rep_buttons.nth(0).get_attribute("class") or ""
    assert "se-is-selected" not in first_classes, (
        "First image should NOT be representative after switching"
    )


# ---------------------------------------------------------------------------
# E2E: Title → Body → Publish trigger → Publish confirm (full sequence)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_full_post_sequence(page: Page):
    """
    Full sequence test:
      1. Navigate to write page
      2. Wait for editor
      3. Click title area and type text
      4. Click body area and type text
      5. Click publish trigger button (opens popover)
      6. Click publish confirm button (actually publishes)

    WARNING: This test publishes a real post. Delete it afterward.
    Must be explicitly run with:
        pytest tests/test_blog_e2e.py::test_full_post_sequence -m "e2e and slow"
    """
    frame = page.frame_locator(selectors.MAIN_FRAME).first

    # Step 1. Navigate
    page.goto(settings.write_url)

    # Step 2. Wait for editor
    wait_for_editor(page)

    # Step 3. Fill title
    title_el = frame.locator(selectors.TITLE_XPATH).first
    title_el.wait_for(state="visible", timeout=5_000)
    title_el.click()
    page.keyboard.type("[자동화 테스트] Playwright로 작성한 포스트")

    # Step 4. Fill body
    body_el = frame.locator(selectors.BODY_XPATH).first
    body_el.wait_for(state="visible", timeout=5_000)
    body_el.click()
    page.keyboard.type(
        "안녕하세요! 이 글은 Playwright 자동화 테스트로 작성된 포스트입니다.\n\n"
        "테스트 항목:\n"
        "- 제목 입력 확인\n"
        "- 본문 입력 확인\n"
        "- 발행 버튼 노출 확인\n\n"
        "테스트 완료 후 삭제 예정입니다."
    )

    # Step 5. Open publish popover
    trigger_el = frame.locator(selectors.PUBLISH_TRIGGER_XPATH).first
    trigger_el.wait_for(state="visible", timeout=5_000)
    trigger_el.click()

    # Step 6. Confirm publish
    confirm_el = frame.locator(f"[data-testid='{selectors.PUBLISH_CONFIRM_TESTID}']").first
    confirm_el.wait_for(state="visible", timeout=5_000)
    confirm_el.click()


@pytest.mark.e2e
@pytest.mark.slow
def test_title_and_body_visible_before_publish(page: Page):
    """
    Safe version: fills title and body, verifies publish trigger is visible
    — but does NOT publish. Use this to validate selector health.
    """
    page.goto(settings.write_url)
    wait_for_editor(page)

    fill_title(page, "[자동화 테스트] Playwright로 작성한 포스트")
    fill_body(page, "자동화 테스트 본문입니다. 발행하지 않습니다.")

    trigger_el = page.frame_locator(selectors.MAIN_FRAME).first \
                     .locator(selectors.PUBLISH_TRIGGER_XPATH).first
    trigger_el.wait_for(state="visible", timeout=5_000)
    assert trigger_el.is_visible(), "Publish trigger button should be visible"
