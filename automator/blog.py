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
