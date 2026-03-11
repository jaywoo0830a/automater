"""
automator/blog.py
-----------------
Core Naver Blog automation logic using Playwright.
All selector strategies avoid hardcoded UUIDs (SE-{uuid} pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, Browser, BrowserContext, expect
from automator.config import settings


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BlogPost:
    title: str
    content: str
    category: str | None = None


# ---------------------------------------------------------------------------
# Stable selector constants
# ---------------------------------------------------------------------------

# iframe that wraps the Smart Editor
EDITOR_IFRAME = "iframe#mainFrame"

# Placeholder spans appear in DOM order: 0 = title, 1 = body
# Using class-based selector avoids UUID dependency entirely.
PLACEHOLDER_SELECTOR = "span.se-placeholder.__se_placeholder"

# Parent editable blocks: id starts with "SE-" (UUID portion is ignored)
EDITABLE_BLOCK_SELECTOR = "[id^='SE-']"

# Publish button in the top toolbar
PUBLISH_BUTTON_TEXT = "발행"

# Naver login URL
LOGIN_URL = "https://nid.naver.com/nidlogin.login"

# Blog write URL
WRITE_URL = "https://blog.naver.com/PostWriteForm.naver"


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def session_exists(session_path: str | Path = "session_state.json") -> bool:
    """Return True if a saved Playwright session file exists."""
    return Path(session_path).exists()


def localized_context(browser: Browser, session_path: str | Path | None = None) -> BrowserContext:
    """
    Create a BrowserContext with localization settings loaded from .env.

    Applies locale, timezone, language (Accept-Language header),
    geolocation, and optional user-agent override — all from settings.

    Args:
        browser:      A Playwright Browser instance.
        session_path: Path to session_state.json. Uses settings default if None.

    Returns:
        A fully configured BrowserContext ready for automation.
    """
    path = Path(session_path) if session_path else settings.session_path

    # Build extra HTTP headers for regional appearance
    extra_headers = {"Accept-Language": f"{settings.language},{settings.locale[:2]};q=0.9"}

    context_kwargs: dict = {
        "locale": settings.locale,
        "timezone_id": settings.timezone,
        "extra_http_headers": extra_headers,
        "geolocation": {
            "latitude": settings.geolocation.latitude,
            "longitude": settings.geolocation.longitude,
        },
        "permissions": ["geolocation"],
    }

    # Apply user-agent override only when explicitly set
    if settings.user_agent:
        context_kwargs["user_agent"] = settings.user_agent

    # Apply saved session when available
    if path.exists():
        context_kwargs["storage_state"] = str(path)

    return browser.new_context(**context_kwargs)


# ---------------------------------------------------------------------------
# Page-level actions
# ---------------------------------------------------------------------------

def wait_for_editor(page: Page, timeout: int = 15_000) -> None:
    """Block until the Smart Editor iframe and its content are visible."""
    frame = page.frame_locator(EDITOR_IFRAME)
    frame.locator(".se-content").wait_for(state="visible", timeout=timeout)


def fill_title(page: Page, title: str, timeout: int = 5_000) -> None:
    """
    Click the title placeholder block and type the given title.
    Targets nth(0) of the placeholder selector — stable across renders.
    """
    frame = page.frame_locator(EDITOR_IFRAME)
    title_block = (
        frame.locator(PLACEHOLDER_SELECTOR)
        .nth(0)
        .locator("..")          # navigate to the parent editable element
    )
    title_block.wait_for(state="visible", timeout=timeout)
    title_block.click()
    page.keyboard.type(title)


def fill_body(page: Page, content: str, timeout: int = 5_000) -> None:
    """
    Click the body placeholder block and type the given content.
    Targets nth(1) of the placeholder selector — stable across renders.
    """
    frame = page.frame_locator(EDITOR_IFRAME)
    body_block = (
        frame.locator(PLACEHOLDER_SELECTOR)
        .nth(1)
        .locator("..")
    )
    body_block.wait_for(state="visible", timeout=timeout)
    body_block.click()
    page.keyboard.type(content)


def click_publish(page: Page, timeout: int = 5_000) -> None:
    """Click the publish button in the top toolbar."""
    btn = page.get_by_text(PUBLISH_BUTTON_TEXT, exact=True)
    btn.wait_for(state="visible", timeout=timeout)
    btn.click()


def post_blog(page: Page, post: BlogPost) -> None:
    """
    Full workflow: navigate → wait for editor → fill title → fill body → publish.

    Args:
        page:  An already-authenticated Playwright Page instance.
        post:  BlogPost dataclass with title and content.
    """
    page.goto(WRITE_URL)
    wait_for_editor(page)
    fill_title(page, post.title)
    fill_body(page, post.content)
    click_publish(page)
