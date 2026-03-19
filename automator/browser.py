"""
automator/browser.py
--------------------
Browser context creation and frame detection utilities.

Selector strings have moved to selectors/naver/editor.json.
This module only owns structural constants (iframe paths) and
infrastructure helpers that are not selector-dependent.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, BrowserContext

from automator.config import BrowserSettings, browser_settings
from automator.options import AccountOption


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------

def build_context(
    browser: Browser,
    account: AccountOption,
    settings: BrowserSettings | None = None,
) -> BrowserContext:
    """
    Create a localized BrowserContext for the given account and settings.

    Loads storage state from account.resolved_session_path when the file exists.

    Args:
        browser:  Playwright Browser instance.
        account:  Account credentials and session path.
        settings: Browser localization settings. Defaults to module-level
                  browser_settings loaded from .env.
    """
    cfg = settings or browser_settings

    context_kwargs: dict = {
        "locale":      cfg.locale,
        "timezone_id": cfg.timezone,
        "extra_http_headers": {
            "Accept-Language": f"{cfg.language},{cfg.locale[:2]};q=0.9"
        },
    }

    session_path = Path(account.resolved_session_path)
    if session_path.exists():
        context_kwargs["storage_state"] = str(session_path)

    if cfg.user_agent:
        context_kwargs["user_agent"] = cfg.user_agent

    return browser.new_context(**context_kwargs)
