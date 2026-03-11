"""
automator/config.py
-------------------
Loads and validates all environment variables including localization settings.
Usage:
    from automator.config import settings
    print(settings.naver_blog_id)  # "rlawjddn00az"
    print(settings.locale)         # "ko_KR"
    print(settings.timezone)       # "Asia/Seoul"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Geolocation helper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Geolocation:
    latitude: float
    longitude: float

    @classmethod
    def from_string(cls, value: str) -> "Geolocation":
        """Parse 'latitude,longitude' string into a Geolocation instance."""
        try:
            lat, lng = value.split(",")
            return cls(latitude=float(lat.strip()), longitude=float(lng.strip()))
        except (ValueError, AttributeError) as e:
            raise ValueError(
                f"GEOLOCATION must be 'latitude,longitude' (e.g. 37.5665,126.9780), got: {value!r}"
            ) from e


# ---------------------------------------------------------------------------
# Main settings dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    # Credentials
    naver_id:      str
    naver_pw:      str
    naver_blog_id: str   # Blog ID used to construct WRITE_URL
    session_path:  Path

    # Localization
    locale:                str         # e.g. "ko_KR", "en_US", "ja_JP"
    timezone:              str         # e.g. "Asia/Seoul", "America/New_York"
    language:              str         # e.g. "ko", "en", "ja"
    geolocation:           Geolocation
    timezone_offset_hours: int         # UTC offset for timestamp composition
    user_agent:            str | None  # None = use Playwright default

    @property
    def write_url(self) -> str:
        """Construct the blog write URL from naver_blog_id."""
        return f"https://blog.naver.com/{self.naver_blog_id}?Redirect=Write&"


def _load_settings() -> Settings:
    """Read all variables from environment / .env and return a Settings instance."""
    geo_raw        = os.getenv("GEOLOCATION", "37.5665,126.9780")
    user_agent_raw = os.getenv("USER_AGENT", "").strip()

    return Settings(
        naver_id=os.getenv("NAVER_ID", ""),
        naver_pw=os.getenv("NAVER_PW", ""),
        naver_blog_id=os.getenv("NAVER_BLOG_ID", ""),
        session_path=Path(os.getenv("SESSION_PATH", "session_state.json")),

        locale=os.getenv("LOCALE", "ko_KR"),
        timezone=os.getenv("TIMEZONE", "Asia/Seoul"),
        language=os.getenv("LANGUAGE", "ko"),
        geolocation=Geolocation.from_string(geo_raw),
        timezone_offset_hours=int(os.getenv("TIMEZONE_OFFSET_HOURS", "9")),
        user_agent=user_agent_raw or None,
    )


# Module-level singleton — import this everywhere
settings = _load_settings()
