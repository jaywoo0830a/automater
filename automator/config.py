"""
automator/config.py
-------------------
Browser localization settings only.

Account credentials have moved to AccountOption in options.py.
config.py owns only the settings that describe *how the browser behaves*,
not *who is logging in*.

Usage:
    from automator.config import browser_settings
    print(browser_settings.locale)    # "ko_KR"
    print(browser_settings.timezone)  # "Asia/Seoul"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Geolocation helper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Geolocation:
    latitude:  float
    longitude: float

    @classmethod
    def from_string(cls, value: str) -> "Geolocation":
        """Parse 'latitude,longitude' string into a Geolocation instance."""
        try:
            lat, lng = value.split(",")
            return cls(latitude=float(lat.strip()), longitude=float(lng.strip()))
        except (ValueError, AttributeError) as e:
            raise ValueError(
                f"GEOLOCATION must be 'latitude,longitude' "
                f"(e.g. 37.5665,126.9780), got: {value!r}"
            ) from e


# ---------------------------------------------------------------------------
# BrowserSettings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BrowserSettings:
    """
    Localization and browser-fingerprint settings.

    Passed to Playwright's new_context(). Does not contain account credentials.
    """
    locale:                str
    timezone:              str
    language:              str
    geolocation:           Geolocation
    timezone_offset_hours: int
    user_agent:            str | None


def _load_browser_settings() -> BrowserSettings:
    """Read localization variables from environment / .env."""
    geo_raw        = os.getenv("GEOLOCATION", "37.5665,126.9780")
    user_agent_raw = os.getenv("USER_AGENT", "").strip()

    return BrowserSettings(
        locale=os.getenv("LOCALE", "ko_KR"),
        timezone=os.getenv("TIMEZONE", "Asia/Seoul"),
        language=os.getenv("LANGUAGE", "ko"),
        geolocation=Geolocation.from_string(geo_raw),
        timezone_offset_hours=int(os.getenv("TIMEZONE_OFFSET_HOURS", "9")),
        user_agent=user_agent_raw or None,
    )


# Module-level singleton
browser_settings = _load_browser_settings()

# Backward-compatibility alias (old code imported `settings`)
settings = browser_settings


# ---------------------------------------------------------------------------
# Application environment
# ---------------------------------------------------------------------------

AppEnv = Literal["test", "dev", "production"]

_VALID_ENVS: frozenset[str] = frozenset({"test", "dev", "production"})


def get_app_env() -> AppEnv:
    """
    Return the current application environment from the ENV variable.

    Defaults to "dev" when ENV is not set or unrecognised.

    Values:
        "test"       — CI / automated testing
        "dev"        — local development
        "production" — live deployment; real external API calls are made
    """
    raw = os.getenv("ENV", "dev").strip().lower()
    if raw not in _VALID_ENVS:
        import warnings
        warnings.warn(
            f"Unknown ENV value {raw!r}. Expected one of {sorted(_VALID_ENVS)}. "
            f"Falling back to 'dev'.",
            stacklevel=2,
        )
        return "dev"
    return raw  # type: ignore[return-value]


def is_production() -> bool:
    """Return True only when ENV=production."""
    return get_app_env() == "production"
