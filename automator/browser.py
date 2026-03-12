"""
automator/browser.py
--------------------
Browser utilities: DOM constants, context creation, and frame helpers.

Everything here is Playwright-specific infrastructure with no business logic.
blog.py imports from here; nothing outside automator/ needs to import directly.

Contents:
  Constants         — structurally stable DOM/CSS selectors
  LOGIN_URL         — Naver login page URL
  localized_context — creates a localized BrowserContext for a session
  session_exists    — checks whether a saved session file exists
  _editor_frame     — detects iframe vs page-level Smart Editor layout
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page, Browser, BrowserContext

from automator.config import settings


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# ---------------------------------------------------------------------------
# DOM constants
# Stable CSS selectors that represent Smart Editor structure.
# These change only when Naver redesigns the editor itself (rare).
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

# Overlays that can block pointer events
POPUP_CANCEL_BUTTON = "button.se-popup-button-cancel"
HELP_CLOSE_BUTTON   = "button.se-help-panel-close-button"


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def session_exists(session_path: str | Path = "session_state.json") -> bool:
    """Return True if a saved Playwright session file exists."""
    return Path(session_path).exists()


# ---------------------------------------------------------------------------
# Context creation
# ---------------------------------------------------------------------------

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
# Frame helpers
# ---------------------------------------------------------------------------

def editor_frame(page: Page):
    """
    Return the context (FrameLocator or Page) that contains the Smart Editor.

    Naver Blog has gone through structural changes over the years:
      - Legacy: editor lives inside #mainFrame iframe
      - Current: editor may live directly on the page (no iframe)

    Probes for #mainFrame within 1 second. Returns page.frame_locator(MAIN_FRAME).first
    when found; returns the page itself otherwise. All downstream locator calls work
    identically regardless of whether an iframe is present.
    """
    try:
        page.frame_locator(MAIN_FRAME) \
            .locator(EDITOR_CONTENT) \
            .wait_for(state="visible", timeout=1_000)
        return page.frame_locator(MAIN_FRAME).first
    except Exception:
        return page


def editor_js_frame(page: Page):
    """
    Return the actual Frame object for JavaScript evaluate() calls.

    FrameLocator.first does not expose evaluate() — this walks page.frames
    to find the editor iframe's Frame object. Falls back to page.main_frame
    when no iframe is present (page-level editor).
    """
    return next(
        (f for f in page.frames if f != page.main_frame),
        page.main_frame,
    )
