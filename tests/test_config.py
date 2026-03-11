"""
tests/test_config.py
--------------------
Unit tests for automator.config — localization settings loading and validation.
"""

import os
import pytest
from unittest.mock import patch
from dataclasses import FrozenInstanceError

from automator.config import Geolocation, Settings, _load_settings


# ---------------------------------------------------------------------------
# Geolocation.from_string
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_geolocation_parses_seoul():
    """Test that Seoul coordinates parse correctly."""
    geo = Geolocation.from_string("37.5665,126.9780")
    assert geo.latitude == 37.5665
    assert geo.longitude == 126.9780


@pytest.mark.unit
def test_geolocation_parses_negative_longitude():
    """Test that negative longitude (e.g. New York) parses correctly."""
    geo = Geolocation.from_string("40.7128,-74.0060")
    assert geo.latitude == 40.7128
    assert geo.longitude == -74.0060


@pytest.mark.unit
def test_geolocation_parses_with_spaces():
    """Test that spaces around the comma are tolerated."""
    geo = Geolocation.from_string("35.6762, 139.6503")
    assert geo.latitude == 35.6762
    assert geo.longitude == 139.6503


@pytest.mark.unit
def test_geolocation_raises_on_invalid_format():
    """Test that a malformed string raises ValueError."""
    with pytest.raises(ValueError, match="GEOLOCATION must be"):
        Geolocation.from_string("not_a_coordinate")


@pytest.mark.unit
def test_geolocation_raises_on_single_value():
    """Test that a string with only one value raises ValueError."""
    with pytest.raises(ValueError):
        Geolocation.from_string("37.5665")


@pytest.mark.unit
def test_geolocation_is_immutable():
    """Test that Geolocation is frozen (no accidental mutation)."""
    geo = Geolocation(latitude=37.5665, longitude=126.9780)
    with pytest.raises((FrozenInstanceError, TypeError)):
        geo.latitude = 0.0  # type: ignore


# ---------------------------------------------------------------------------
# _load_settings — environment variable mapping
# ---------------------------------------------------------------------------

MOCK_ENV = {
    "NAVER_ID":              "test_user",
    "NAVER_PW":              "test_pass",
    "SESSION_PATH":          "test_session.json",
    "LOCALE":                "en_US",
    "TIMEZONE":              "America/New_York",
    "LANGUAGE":              "en",
    "GEOLOCATION":           "40.7128,-74.0060",
    "TIMEZONE_OFFSET_HOURS": "-5",
    "USER_AGENT":            "Mozilla/5.0 TestAgent",
}


@pytest.mark.unit
def test_settings_loads_locale(monkeypatch: pytest.MonkeyPatch):
    """Test that LOCALE env var is reflected in settings.locale."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.locale == "en_US"


@pytest.mark.unit
def test_settings_loads_timezone(monkeypatch: pytest.MonkeyPatch):
    """Test that TIMEZONE env var is reflected in settings.timezone."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.timezone == "America/New_York"


@pytest.mark.unit
def test_settings_loads_language(monkeypatch: pytest.MonkeyPatch):
    """Test that LANGUAGE env var is reflected in settings.language."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.language == "en"


@pytest.mark.unit
def test_settings_loads_geolocation(monkeypatch: pytest.MonkeyPatch):
    """Test that GEOLOCATION env var is parsed into a Geolocation object."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.geolocation.latitude == 40.7128
    assert s.geolocation.longitude == -74.0060


@pytest.mark.unit
def test_settings_loads_timezone_offset(monkeypatch: pytest.MonkeyPatch):
    """Test that TIMEZONE_OFFSET_HOURS is parsed as an integer."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.timezone_offset_hours == -5


@pytest.mark.unit
def test_settings_loads_user_agent(monkeypatch: pytest.MonkeyPatch):
    """Test that USER_AGENT env var is reflected in settings.user_agent."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    assert s.user_agent == "Mozilla/5.0 TestAgent"


@pytest.mark.unit
def test_settings_user_agent_empty_becomes_none(monkeypatch: pytest.MonkeyPatch):
    """Test that an empty USER_AGENT string is normalized to None."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("USER_AGENT", "")
    s = _load_settings()
    assert s.user_agent is None


@pytest.mark.unit
def test_settings_korean_defaults(monkeypatch: pytest.MonkeyPatch):
    """Test that Korean defaults apply when no env vars are set."""
    # Remove all localization env vars to test defaults
    for key in MOCK_ENV:
        monkeypatch.delenv(key, raising=False)
    s = _load_settings()
    assert s.locale == "ko_KR"
    assert s.timezone == "Asia/Seoul"
    assert s.language == "ko"
    assert s.timezone_offset_hours == 9
    assert s.geolocation.latitude == 37.5665
    assert s.geolocation.longitude == 126.9780


@pytest.mark.unit
def test_settings_is_immutable(monkeypatch: pytest.MonkeyPatch):
    """Test that Settings is frozen — no accidental mutation."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    s = _load_settings()
    with pytest.raises((FrozenInstanceError, TypeError)):
        s.locale = "zh_CN"  # type: ignore


# ---------------------------------------------------------------------------
# naver_blog_id and write_url
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_settings_loads_naver_blog_id(monkeypatch: pytest.MonkeyPatch):
    """Test that NAVER_BLOG_ID env var is reflected in settings.naver_blog_id."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("NAVER_BLOG_ID", "rlawjddn00az")
    s = _load_settings()
    assert s.naver_blog_id == "rlawjddn00az"


@pytest.mark.unit
def test_write_url_uses_naver_blog_id(monkeypatch: pytest.MonkeyPatch):
    """Test that write_url is constructed from naver_blog_id, not hardcoded."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("NAVER_BLOG_ID", "rlawjddn00az")
    s = _load_settings()
    assert s.write_url == "https://blog.naver.com/rlawjddn00az?Redirect=Write&"


@pytest.mark.unit
def test_write_url_changes_with_different_blog_id(monkeypatch: pytest.MonkeyPatch):
    """Test that changing NAVER_BLOG_ID produces a different write_url."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("NAVER_BLOG_ID", "another_user")
    s = _load_settings()
    assert "another_user" in s.write_url
    assert "rlawjddn00az" not in s.write_url


@pytest.mark.unit
def test_write_url_contains_redirect_param(monkeypatch: pytest.MonkeyPatch):
    """Test that write_url always includes the Redirect=Write query param."""
    for k, v in MOCK_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("NAVER_BLOG_ID", "rlawjddn00az")
    s = _load_settings()
    assert "Redirect=Write" in s.write_url
