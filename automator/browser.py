"""
automator/browser.py
--------------------
Browser context creation with anti-detection support.

Accepts a DSL browser config dict and applies:
    - viewport, user_agent, locale, timezone, geolocation
    - fingerprint stealth scripts via add_init_script()
    - session state loading
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser, BrowserContext

from automator.stealth import build_stealth_script

# ---------------------------------------------------------------------------
# Default browser config
# ---------------------------------------------------------------------------

DEFAULT_BROWSER_CONFIG: dict[str, Any] = {
    "viewport": [1920, 1080],
    "user_agent": None,
    "locale": "ko-KR",
    "timezone": "Asia/Seoul",
    "color_scheme": "light",
    "device_scale_factor": 1,
    "geolocation": None,
    "fingerprint": {
        "webdriver": False,
        "plugins": True,
        "chrome_runtime": True,
        "languages": True,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_context(
    browser: Browser,
    browser_config: dict[str, Any] | None = None,
    storage_state: dict | str | None = None,
) -> BrowserContext:
    """
    Create a BrowserContext with anti-detection settings.

    Args:
        browser:        Playwright Browser instance.
        browser_config: DSL browser config dict. Merged over DEFAULT_BROWSER_CONFIG.
        storage_state:  Playwright storage state (session data).

    Returns:
        Configured BrowserContext with stealth scripts injected.
    """
    cfg = {**DEFAULT_BROWSER_CONFIG, **(browser_config or {})}

    locale = str(cfg.get("locale", "ko-KR"))
    timezone = str(cfg.get("timezone", "Asia/Seoul"))
    lang = locale.split("-")[0] if "-" in locale else locale.split("_")[0]

    viewport_raw = cfg.get("viewport", [1920, 1080])
    if isinstance(viewport_raw, (list, tuple)) and len(viewport_raw) >= 2:
        viewport = {"width": int(viewport_raw[0]), "height": int(viewport_raw[1])}
    else:
        viewport = {"width": 1920, "height": 1080}

    context_kwargs: dict[str, Any] = {
        "viewport": viewport,
        "locale": locale,
        "timezone_id": timezone,
        "color_scheme": cfg.get("color_scheme", "light"),
        "device_scale_factor": int(cfg.get("device_scale_factor", 1)),
        "extra_http_headers": {
            "Accept-Language": f"{locale},{lang};q=0.9",
        },
    }

    # user agent
    ua = cfg.get("user_agent")
    if ua:
        context_kwargs["user_agent"] = str(ua)

    # geolocation
    geo = cfg.get("geolocation")
    if isinstance(geo, (list, tuple)) and len(geo) >= 2:
        context_kwargs["geolocation"] = {
            "latitude": float(geo[0]),
            "longitude": float(geo[1]),
        }
        context_kwargs["permissions"] = ["geolocation"]

    # session state
    if storage_state:
        context_kwargs["storage_state"] = storage_state

    ctx = browser.new_context(**context_kwargs)

    # stealth script injection
    fingerprint = cfg.get("fingerprint", {})
    script = build_stealth_script(fingerprint, locale)
    if script:
        ctx.add_init_script(script)

    return ctx


def merge_browser_config(
    global_config: dict[str, Any],
    account_config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge account-level browser overrides into global browser config.

    Fingerprint is deep-merged (individual keys override, not whole dict).
    """
    if not account_config:
        return dict(global_config)

    merged = {**global_config, **account_config}

    # deep-merge fingerprint
    global_fp = global_config.get("fingerprint", {})
    account_fp = account_config.get("fingerprint", {})
    if global_fp or account_fp:
        merged["fingerprint"] = {**global_fp, **account_fp}

    return merged
