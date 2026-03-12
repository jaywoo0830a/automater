"""
tests/test_debug.py
-------------------
임시 진단 테스트 모음.

문제 해결 후 이 파일의 테스트들은 삭제한다.
실행: pytest tests/test_debug.py -m e2e -v -s
"""
import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import Page

from automator.config import settings
from automator.blog import (
    MAIN_FRAME,
    EDITOR_CONTENT,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    wait_for_editor,
    upload_image,
)

load_dotenv()

SESSION_PATH     = os.getenv("SESSION_PATH", "session_state.json")
EDITOR_JSON_PATH = os.getenv("EDITOR_JSON_PATH", "selectors/naver/editor.json")
IMAGE_PATH       = os.getenv("TEST_IMAGE_PATH", "smile.jpg")


# ---------------------------------------------------------------------------
# page fixture (test_blog_e2e.py와 동일한 구조)
# ---------------------------------------------------------------------------

from playwright.sync_api import sync_playwright, Browser, BrowserContext
from automator.blog import session_exists, login
import os

NAVER_ID = os.getenv("NAVER_ID", "")
NAVER_PW = os.getenv("NAVER_PW", "")
LOGIN_JSON_PATH = os.getenv("LOGIN_JSON_PATH", "selectors/naver/login.json")


@pytest.fixture(scope="module")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def auth_context(browser_instance: Browser):
    if session_exists(SESSION_PATH):
        ctx = browser_instance.new_context(storage_state=SESSION_PATH)
    elif NAVER_ID and NAVER_PW:
        ctx = browser_instance.new_context()
        pg  = ctx.new_page()
        login(pg, NAVER_ID, NAVER_PW, LOGIN_JSON_PATH)
        ctx.storage_state(path=SESSION_PATH)
        pg.close()
    else:
        pytest.skip("No session or credentials available")
    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext):
    pg = auth_context.new_page()
    pg.goto(settings.write_url)
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# 진단: rep 버튼 클릭 전략 테스트
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_rep_button_js_click(page: Page):
    """
    JavaScript dispatchEvent로 rep 버튼을 직접 클릭한다.
    Playwright의 visibility 체크를 우회하여 hidden 버튼도 강제 클릭 가능한지 확인.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    wait_for_editor(page)
    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    # Get the actual iframe Frame object
    frame = next(
        (f for f in page.frames if f != page.main_frame and "se-content" in (f.content() or "")),
        None
    )
    if frame is None:
        # Fallback: find by URL pattern
        frame = next(
            (f for f in page.frames if f != page.main_frame),
            None
        )

    assert frame is not None, "Could not find editor iframe"

    # Check button count and visibility state
    btn_count  = frame.locator(REP_IMAGE_BUTTON).count()
    is_visible = frame.locator(REP_IMAGE_BUTTON).first.is_visible()
    print(f"\n  rep button count : {btn_count}")
    print(f"  first btn visible: {is_visible}")

    # Try JS click — bypasses CSS visibility
    result = frame.evaluate("""(selector) => {
        const btns = document.querySelectorAll(selector);
        if (!btns.length) return 'no buttons found';
        const btn = btns[0];
        const before = btn.classList.contains('se-is-selected');
        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        const after = btn.classList.contains('se-is-selected');
        return `before=${before} after=${after} class=${btn.className}`;
    }""", REP_IMAGE_BUTTON)

    print(f"  JS click result  : {result}")

    # Check if selected class appeared
    selected_count = frame.locator(REP_IMAGE_BUTTON_SELECTED).count()
    print(f"  selected count   : {selected_count}")

    assert selected_count >= 1, f"Expected se-is-selected button after JS click, got {selected_count}"
