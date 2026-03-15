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


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------

def build_context(
    browser: Browser,
    account,   # AccountOption — imported at call site to avoid circular import
    runtime,   # RuntimeOption
) -> BrowserContext:
    """
    Create a localized BrowserContext for the given account and runtime.

    Loads storage state from account.session_path when the file exists.
    """
    context_kwargs: dict = {
        "locale":      runtime.locale,
        "timezone_id": runtime.timezone,
        "extra_http_headers": {
            "Accept-Language": f"{runtime.language},{runtime.locale[:2]};q=0.9"
        },
    }

    if account.session_exists():
        context_kwargs["storage_state"] = str(account.session_path)

    return browser.new_context(**context_kwargs)
