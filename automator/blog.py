"""
automator/blog.py
-----------------
Core Naver Blog automation logic using Playwright.
All selector strings are imported from automator.selectors — update
selectors there when the Naver editor DOM changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, Browser, BrowserContext

from automator.config import settings
from automator import selectors


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BlogPost:
    title: str
    content: str
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


def localized_context(browser: Browser, session_path: str | Path | None = None) -> BrowserContext:
    """
    Create a BrowserContext with localization settings loaded from .env.
    Applies locale, timezone, Accept-Language header, geolocation,
    and optional user-agent override.
    """
    path = Path(session_path) if session_path else settings.session_path

    context_kwargs: dict = {
        "locale": settings.locale,
        "timezone_id": settings.timezone,
        "extra_http_headers": {
            "Accept-Language": f"{settings.language},{settings.locale[:2]};q=0.9"
        },
        "geolocation": {
            "latitude": settings.geolocation.latitude,
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

def login(page: Page, naver_id: str, naver_pw: str, timeout: int = 15_000) -> None:
    """
    Perform Naver ID/PW login and navigate to the blog write page.

    After the login form submits, Naver redirects to www.naver.com.
    This function waits for that redirect to complete, verifies login
    succeeded, then navigates to the blog write URL so subsequent
    actions (editor, publish) can proceed without interruption.

    NOTE: Naver may show a CAPTCHA or 2FA — handle manually if needed.
    """
    page.goto(LOGIN_URL)
    page.locator("#id").fill(naver_id)
    page.locator("#pw").fill(naver_pw)
    page.get_by_text("로그인", exact=True).click()

    # Wait until the browser leaves the login page.
    # "networkidle" is unusable here — www.naver.com streams ads,
    # websockets, and real-time widgets that never go idle.
    page.wait_for_url(lambda url: "nidlogin" not in url, timeout=timeout)
    page.wait_for_load_state("domcontentloaded", timeout=timeout)

    # Navigate to blog write page so session is fully established
    page.goto(settings.write_url)
    page.wait_for_load_state("domcontentloaded", timeout=timeout)


def upload_image(page: Page, image_path: str, timeout: int = 10_000) -> None:
    """
    Upload an image to the blog editor via the toolbar button.

    Clicks the image upload trigger in the editor toolbar, intercepts
    the OS file chooser dialog using Playwright's expect_file_chooser,
    and sets the given file. After upload, waits for the image element
    to appear inside the editor content area.

    Args:
        page:       An already-authenticated Page with the editor loaded.
        image_path: Absolute or relative path to the image file.
        timeout:    Max wait time in ms for the image to appear.

    Raises:
        FileNotFoundError: If image_path does not exist.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path!r}")

    frame = page.frame_locator(selectors.MAIN_FRAME).first
    trigger = frame.locator(selectors.IMAGE_UPLOAD_TRIGGER_XPATH).first
    trigger.wait_for(state="visible", timeout=timeout)

    # Intercept the file chooser dialog and inject the image file
    with page.expect_file_chooser() as fc_info:
        trigger.click()
    file_chooser = fc_info.value
    file_chooser.set_files(str(path))

    # Wait for the uploaded image to render in the editor
    frame.locator(selectors.UPLOADED_IMAGE).first.wait_for(
        state="visible", timeout=timeout
    )

def wait_for_editor(page: Page, timeout: int = 15_000) -> None:
    """Block until the Smart Editor iframe and its content are visible."""
    page.frame_locator(selectors.MAIN_FRAME) \
        .locator(selectors.EDITOR_CONTENT) \
        .wait_for(state="visible", timeout=timeout)


def fill_title(page: Page, title: str, timeout: int = 5_000) -> None:
    """
    Click the title area and type the given title.
    Update selectors.TITLE_XPATH when the editor DOM changes.
    """
    el = page.frame_locator(selectors.MAIN_FRAME).first \
             .locator(selectors.TITLE_XPATH).first
    el.wait_for(state="visible", timeout=timeout)
    el.click()
    page.keyboard.type(title)


def fill_body(page: Page, content: str, timeout: int = 5_000) -> None:
    """
    Click the body area and type the given content.
    Update selectors.BODY_XPATH when the editor DOM changes.
    """
    el = page.frame_locator(selectors.MAIN_FRAME).first \
             .locator(selectors.BODY_XPATH).first
    el.wait_for(state="visible", timeout=timeout)
    el.click()
    page.keyboard.type(content)


def click_publish_trigger(page: Page, timeout: int = 5_000) -> None:
    """
    Click the publish trigger button to open the publish popover.
    Update selectors.PUBLISH_TRIGGER_XPATH when the editor DOM changes.
    """
    el = page.frame_locator(selectors.MAIN_FRAME).first \
             .locator(selectors.PUBLISH_TRIGGER_XPATH).first
    el.wait_for(state="visible", timeout=timeout)
    el.click()


def click_publish_confirm(page: Page, timeout: int = 5_000) -> None:
    """
    Click the publish confirm button inside the popover.
    Targets data-testid — most stable selector available.
    Update selectors.PUBLISH_CONFIRM_TESTID if the attribute changes.
    """
    el = page.frame_locator(selectors.MAIN_FRAME).first \
             .locator(f"[data-testid='{selectors.PUBLISH_CONFIRM_TESTID}']").first
    el.wait_for(state="visible", timeout=timeout)
    el.click()


def post_blog(page: Page, post: BlogPost) -> None:
    """
    Full publish workflow:
      navigate → wait for editor → fill title → fill body
      → open publish popover → confirm publish

    Args:
        page: An already-authenticated Playwright Page instance.
        post: BlogPost dataclass with title and content.
    """
    page.goto(settings.write_url)
    wait_for_editor(page)
    fill_title(page, post.title)
    fill_body(page, post.content)
    click_publish_trigger(page)
    click_publish_confirm(page)
