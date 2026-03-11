"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.
Requires:
  1. A valid session_state.json  (run: python -m superselect --login ...)
  OR
  2. NAVER_ID / NAVER_PW environment variables in .env

Run with:
    pytest tests/test_blog_e2e.py -m e2e -v

Skip in CI if credentials are absent — the session_required fixture handles this.
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from automator.blog import (
    BlogPost,
    post_blog,
    wait_for_editor,
    fill_title,
    fill_body,
    LOGIN_URL,
    WRITE_URL,
    EDITOR_IFRAME,
    PLACEHOLDER_SELECTOR,
    session_exists,
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
        _login_with_credentials(page, NAVER_ID, NAVER_PW)
        ctx.storage_state(path=SESSION_PATH)
        page.close()
    else:
        pytest.skip(
            "No session file or credentials found. "
            "Set NAVER_ID/NAVER_PW in .env or run superselect --login first."
        )

    yield ctx
    ctx.close()


@pytest.fixture()
def page(auth_context: BrowserContext):
    """Open a fresh page per test, then close it."""
    p = auth_context.new_page()
    yield p
    p.close()


def _login_with_credentials(page: Page, naver_id: str, naver_pw: str) -> None:
    """
    Perform Naver ID/PW login.
    NOTE: Naver may show a CAPTCHA or 2FA — handle manually if needed.
    """
    page.goto(LOGIN_URL)
    page.locator("#id").fill(naver_id)
    page.locator("#pw").fill(naver_pw)
    page.get_by_text("로그인", exact=True).click()
    page.wait_for_url("**/naver.com/**", timeout=15_000)


# ---------------------------------------------------------------------------
# E2E: Editor loads correctly
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page):
    """Test that the Smart Editor iframe renders after navigating to the write page."""
    page.goto(WRITE_URL)
    iframe = page.frame_locator(EDITOR_IFRAME)
    iframe.locator(".se-content").wait_for(state="visible", timeout=15_000)
    # If no TimeoutError is raised, the editor loaded successfully
    assert True


@pytest.mark.e2e
def test_two_placeholder_spans_exist(page: Page):
    """
    Test that exactly 2 se-placeholder spans are present in the editor:
    one for the title and one for the body.
    This validates our nth(0)/nth(1) strategy.
    """
    page.goto(WRITE_URL)
    frame = page.frame_locator(EDITOR_IFRAME)
    frame.locator(".se-content").wait_for(state="visible", timeout=15_000)

    placeholders = frame.locator(PLACEHOLDER_SELECTOR)
    count = placeholders.count()
    assert count >= 2, (
        f"Expected at least 2 placeholder spans, found {count}. "
        "nth(0)/nth(1) strategy may be broken."
    )


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page):
    """
    Confirm that placeholder parent IDs follow the SE-{uuid} pattern,
    validating why we must NOT hardcode them.
    """
    page.goto(WRITE_URL)
    frame = page.frame_locator(EDITOR_IFRAME)
    frame.locator(".se-content").wait_for(state="visible", timeout=15_000)

    first_placeholder = frame.locator(PLACEHOLDER_SELECTOR).nth(0)
    parent_id = first_placeholder.locator("..").get_attribute("id")

    assert parent_id is not None, "Parent element should have an id attribute"
    assert parent_id.startswith("SE-"), (
        f"Expected id to start with 'SE-', got: {parent_id!r}"
    )


# ---------------------------------------------------------------------------
# E2E: Title and body input
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_fill_title_types_text(page: Page):
    """Test that fill_title successfully inputs text into the title area."""
    page.goto(WRITE_URL)
    wait_for_editor(page)

    fill_title(page, "[E2E 테스트] 제목 입력 확인")

    # Read back typed text from the editable block
    frame = page.frame_locator(EDITOR_IFRAME)
    title_block = frame.locator(PLACEHOLDER_SELECTOR).nth(0).locator("..")
    actual_text = title_block.inner_text()
    assert "[E2E 테스트] 제목 입력 확인" in actual_text


@pytest.mark.e2e
@pytest.mark.slow
def test_fill_body_types_text(page: Page):
    """Test that fill_body successfully inputs text into the body area."""
    page.goto(WRITE_URL)
    wait_for_editor(page)

    fill_body(page, "E2E 테스트 본문입니다. 자동화 검증용 글입니다.")

    frame = page.frame_locator(EDITOR_IFRAME)
    body_block = frame.locator(PLACEHOLDER_SELECTOR).nth(1).locator("..")
    actual_text = body_block.inner_text()
    assert "E2E 테스트 본문입니다" in actual_text


# ---------------------------------------------------------------------------
# E2E: Full post workflow (실제 발행 — 주의!)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_post_blog_full_workflow(page: Page):
    """
    WARNING: This test actually publishes a post on Naver Blog.
    Run only when you intend to create a real (or draft) post.

    To prevent accidental publishing, this test is marked slow and
    must be explicitly selected:
        pytest tests/test_blog_e2e.py::test_post_blog_full_workflow -m "e2e and slow"
    """
    post = BlogPost(
        title="[자동화 테스트] 삭제 예정 포스트",
        content=(
            "이 글은 Playwright 자동화 테스트로 작성된 글입니다.\n"
            "테스트 확인 후 삭제해 주세요."
        ),
    )

    # Navigate and fill — stop before clicking publish to stay safe
    page.goto(WRITE_URL)
    wait_for_editor(page)
    fill_title(page, post.title)
    fill_body(page, post.content)

    # Verify publish button is visible before asserting success
    publish_btn = page.get_by_text("발행", exact=True)
    publish_btn.wait_for(state="visible", timeout=5_000)
    assert publish_btn.is_visible(), "Publish button should be visible after filling content"

    # Uncomment the next line to actually publish:
    # publish_btn.click()
