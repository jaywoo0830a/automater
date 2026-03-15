"""
automator/blog.py
-----------------
Naver Blog automation logic using Playwright.

Selector strings are no longer hardcoded here.
All locators are resolved at runtime from automator-format JSON files:
  - selectors/naver/login.json   (elements outside the editor iframe)
  - selectors/naver/editor.json  (elements inside #mainFrame)

To update selectors when the Naver DOM changes, edit the JSON files only —
no Python code needs to change.
Run scripts/capture_selectors.py to verify selectors are still live.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, Browser, BrowserContext

from automator.config import settings
from automator.selector_loader import SelectorLoader


# ---------------------------------------------------------------------------
# DOM constants — structural selectors that never change with Naver updates
# ---------------------------------------------------------------------------

# The main Smart Editor iframe selector
MAIN_FRAME = "#mainFrame"

# Stable class confirming the editor has loaded
EDITOR_CONTENT = ".se-content"

# CSS selector for an uploaded image inside the editor
UPLOADED_IMAGE = ".se-image-resource"

# The div-level container wrapping each image block.
# Each image lives inside div.se-component.se-image — this is the element
# that responds to hover and reveals the rep button.
IMAGE_COMPONENT = "div.se-component.se-image"

# Structural CSS selectors for rep image buttons — used in e2e tests only.
# These are stable class names that do not change with Naver deployments,
# unlike the UUID-based CSS in editor.json which changes per session.
REP_IMAGE_BUTTON          = "button.se-set-rep-image-button"
REP_IMAGE_BUTTON_SELECTED = "button.se-set-rep-image-button.se-is-selected"


# ---------------------------------------------------------------------------
# Default JSON paths (relative to the project root)
# ---------------------------------------------------------------------------

_DEFAULT_LOGIN_JSON  = Path("selectors/naver/login.json")
_DEFAULT_EDITOR_JSON = Path("selectors/naver/editor.json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _editor_frame(page: Page):
    """
    Return the context (FrameLocator or Page) that contains the Smart Editor.

    Naver Blog has gone through structural changes over the years:
      - Legacy: editor lives inside #mainFrame iframe
      - Current: editor may live directly on the page (no iframe)

    This helper checks whether #mainFrame exists within 1 second.
    If it does, returns page.frame_locator(MAIN_FRAME).first.
    If not, returns the page itself so all downstream locator calls work
    identically regardless of whether an iframe is present.

    All editor functions (fill_title, fill_body, upload_image, etc.)
    call this instead of hardcoding page.frame_locator(MAIN_FRAME).
    """
    try:
        page.frame_locator(MAIN_FRAME) \
            .locator(EDITOR_CONTENT) \
            .wait_for(state="visible", timeout=1_000)
        return page.frame_locator(MAIN_FRAME).first
    except Exception:
        return page


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BlogPost:
    title:    str
    content:  str
    category: str | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def session_exists(session_path: str | Path = "session_state.json") -> bool:
    """Return True if a saved Playwright session file exists."""
    return Path(session_path).exists()


def localized_context(
    browser: Browser,
    session_path: str | Path | None = None,
) -> BrowserContext:
    """
    Create a BrowserContext with localization settings loaded from .env.
    Applies locale, timezone, Accept-Language header, geolocation,
    and optional user-agent override.
    """
    path = Path(session_path) if session_path else settings.session_path

    context_kwargs: dict = {
        "locale":      settings.locale,
        "timezone_id": settings.timezone,
        "extra_http_headers": {
            "Accept-Language": f"{settings.language},{settings.locale[:2]};q=0.9"
        },
        "geolocation": {
            "latitude":  settings.geolocation.latitude,
            "longitude": settings.geolocation.longitude,
        },
        "permissions": ["geolocation"],
    }

    if settings.user_agent:
        context_kwargs["user_agent"] = settings.user_agent

    if path.exists():
        context_kwargs["storage_state"] = str(path)

    return browser.new_context(**context_kwargs)


# ---------------------------------------------------------------------------
# Page-level actions
# ---------------------------------------------------------------------------

def login(
    page:       Page,
    naver_id:   str,
    naver_pw:   str,
    login_json: str | Path = _DEFAULT_LOGIN_JSON,
    timeout:    int = 15_000,
) -> None:
    """
    Perform Naver ID/PW login and navigate to the blog write page.

    Locators are resolved from login_json (superselect format).
    After the login form submits, waits for the redirect away from
    the login page, then navigates to the blog write URL.

    NOTE: Naver may show a CAPTCHA or 2FA — handle manually if needed.
    """
    sel = SelectorLoader.load(login_json)

    page.goto(LOGIN_URL)
    sel.locator(page, "naver_login_id").fill(naver_id)
    sel.locator(page, "naver_login_pw").fill(naver_pw)
    sel.locator(page, "naver_login_submit").click()

    # Wait until the browser leaves the login page.
    # "networkidle" is unusable — www.naver.com streams ads and websockets.
    page.wait_for_url(lambda url: "nidlogin" not in url, timeout=timeout)
    page.wait_for_load_state("domcontentloaded", timeout=timeout)

    # Navigate to blog write page so session is fully established
    page.goto(settings.write_url)
    page.wait_for_load_state("domcontentloaded", timeout=timeout)


def wait_for_editor(
    page:    Page,
    timeout: int = 15_000,
) -> None:
    """
    Block until the Smart Editor content is visible, then dismiss the
    draft-recovery popup if it appears.

    Uses _editor_frame() to handle both iframe and page-level editor layouts.
    The recovery popup cancel button is found via the stable CSS class
    'button.se-popup-button-cancel' — more reliable than get_by_text('취소')
    which can match other elements in the editor.
    """
    # Wait for editor content — _editor_frame() probes for the iframe first
    frame = _editor_frame(page)
    if frame is page:
        # Page-level editor: wait directly
        page.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=timeout)
    else:
        # iframe editor: already confirmed visible inside _editor_frame probe,
        # but do a full-timeout wait here to be safe
        page.frame_locator(MAIN_FRAME) \
            .locator(EDITOR_CONTENT) \
            .wait_for(state="visible", timeout=timeout)

    # Dismiss the draft-recovery popup if it appears.
    # The popup sometimes appears with a delay after the editor loads,
    # so we poll in short intervals for up to POPUP_WAIT_MS total.
    # Each probe uses a short timeout so we don't block unnecessarily when
    # the popup is absent.
    POPUP_WAIT_MS  = 5_000   # total window to watch for the popup
    PROBE_INTERVAL = 200     # ms between each visibility probe
    import time
    deadline = time.monotonic() + POPUP_WAIT_MS / 1_000
    while time.monotonic() < deadline:
        try:
            btn = frame.locator("button.se-popup-button-cancel").first
            btn.wait_for(state="visible", timeout=PROBE_INTERVAL)
            btn.click()
            break   # popup found and dismissed
        except Exception:
            pass    # not visible yet — keep polling

    # Dismiss the help panel if it is open.
    # The panel (article.se-help-panel.se-is-on) lives inside the editor iframe
    # and intercepts pointer events, blocking clicks on the publish button.
    # It appears on first load and stays open until explicitly closed.
    try:
        close_btn = frame.locator("button.se-help-panel-close-button").first
        close_btn.wait_for(state="visible", timeout=2_000)
        close_btn.click()
    except Exception:
        pass    # panel already closed or never opened


def fill_title(
    page:        Page,
    title:       str,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    timeout:     int = 5_000,
) -> None:
    """Click the title area and type the given title."""
    frame = _editor_frame(page)
    sel   = SelectorLoader.load(editor_json)
    el    = sel.locator(frame, "editor_title")
    el.wait_for(state="visible", timeout=timeout)
    el.click()
    page.keyboard.type(title)


def fill_body(
    page:        Page,
    content:     str,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    timeout:     int = 5_000,
) -> None:
    """Click the body area and type the given content."""
    frame = _editor_frame(page)
    sel   = SelectorLoader.load(editor_json)
    el    = sel.locator(frame, "editor_body")
    el.wait_for(state="visible", timeout=timeout)
    el.click()
    page.keyboard.type(content)


def upload_image(
    page:        Page,
    image_path:  str,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    timeout:     int = 10_000,
) -> None:
    """
    Upload an image via the editor toolbar button.

    Raises:
        FileNotFoundError: If image_path does not exist.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path!r}")

    frame   = _editor_frame(page)
    sel     = SelectorLoader.load(editor_json)
    trigger = sel.locator(frame, "image_trigger")
    trigger.wait_for(state="visible", timeout=timeout)

    with page.expect_file_chooser() as fc_info:
        trigger.click()
    fc_info.value.set_files(str(path))

    # After file selection, Naver sometimes opens a media library sidebar.
    # If it appears, close it immediately so the upload can proceed.
    try:
        close_btn = sel.locator(frame, "library_close")
        close_btn.wait_for(state="visible", timeout=3_000)
        close_btn.click()
    except Exception:
        pass  # library did not open — proceed normally

    frame.locator(UPLOADED_IMAGE).first.wait_for(state="visible", timeout=timeout)


def set_representative_image(
    page:    Page,
    index:   int = 0,
    timeout: int = 5_000,
) -> None:
    """
    Set the representative (thumbnail) image by clicking its "대표" button.

    The rep button is hidden by CSS and Playwright's visibility checks prevent
    hover/click from working on buttons beyond index 0. We use JavaScript
    dispatchEvent to click the nth button directly, bypassing CSS visibility.

    After clicking, waits for REP_IMAGE_BUTTON_SELECTED to confirm state.

    Raises:
        ValueError: If index is negative.
    """
    if index < 0:
        raise ValueError(f"index must be >= 0, got {index}")

    frame = _editor_frame(page)

    # Wait until the nth image component is in the DOM
    frame.locator(IMAGE_COMPONENT).nth(index).wait_for(
        state="visible", timeout=timeout
    )

    # Get the actual Frame object for evaluate() — _editor_frame() may return
    # a FrameLocator (.first) which does not have evaluate().
    # Walk page.frames to find the editor iframe.
    editor_frame = next(
        (f for f in page.frames if f != page.main_frame),
        page.main_frame,
    )

    result = editor_frame.evaluate(
        """([selector, idx]) => {
            const btns = document.querySelectorAll(selector);
            if (idx >= btns.length) return `index ${idx} out of range (${btns.length} buttons)`;
            btns[idx].dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
            return btns[idx].classList.contains('se-is-selected') ? 'selected' : 'not-selected';
        }""",
        [REP_IMAGE_BUTTON, index],
    )

    if result != "selected":
        raise RuntimeError(
            f"set_representative_image(index={index}) failed: JS click returned {result!r}"
        )

    frame.locator(REP_IMAGE_BUTTON_SELECTED).first.wait_for(
        state="attached", timeout=timeout
    )


def click_publish_trigger(
    page:        Page,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    timeout:     int = 5_000,
) -> None:
    """
    Click the publish trigger button to open the publish popover.

    The 발행 button lives in the page-level toolbar (outside the editor
    iframe), not inside #mainFrame. Try page directly first; fall back to
    the iframe context if not found.
    """
    sel = SelectorLoader.load(editor_json)

    # Try page-level first (toolbar is outside the iframe)
    try:
        el = sel.locator(page, "publish_trigger")
        el.wait_for(state="visible", timeout=timeout)
        el.click()
        return
    except Exception:
        pass

    # Fallback: try inside the editor frame
    frame = _editor_frame(page)
    el    = sel.locator(frame, "publish_trigger")
    el.wait_for(state="visible", timeout=timeout)
    el.click()


def click_publish_confirm(
    page:        Page,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    timeout:     int = 5_000,
) -> None:
    """
    Click the publish confirm button inside the popover.

    The confirm button appears in a page-level popover (outside the iframe).
    Try page directly first; fall back to the iframe context if not found.
    """
    sel = SelectorLoader.load(editor_json)

    # Try page-level first
    try:
        el = sel.locator(page, "publish_confirm")
        el.wait_for(state="visible", timeout=timeout)
        el.click()
        return
    except Exception:
        pass

    # Fallback: try inside the editor frame
    frame = _editor_frame(page)
    el    = sel.locator(frame, "publish_confirm")
    el.wait_for(state="visible", timeout=timeout)
    el.click()


def post_blog(
    page:        Page,
    post:        BlogPost,
    editor_json: str | Path = _DEFAULT_EDITOR_JSON,
) -> None:
    """
    Full publish workflow:
      navigate → wait for editor → fill title → fill body
      → open publish popover → confirm publish

    Args:
        page:        An already-authenticated Playwright Page.
        post:        BlogPost with title and content.
        editor_json: Path to the superselect editor selector JSON.
    """
    page.goto(settings.write_url)
    wait_for_editor(page)
    fill_title(page, post.title, editor_json)
    fill_body(page, post.content, editor_json)
    click_publish_trigger(page, editor_json)
    click_publish_confirm(page, editor_json)
