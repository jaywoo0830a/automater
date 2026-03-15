"""
tests/test_config.py
--------------------
Unit tests for BrowserSettings and Geolocation (automator/config.py).

AccountOption 테스트는 test_job_unit.py 에 있다.
"""

import pytest
from dataclasses import FrozenInstanceError

from automator.config import Geolocation, _load_browser_settings


# ===========================================================================
# Geolocation.from_string
# ===========================================================================

@pytest.mark.unit
def test_geolocation_parses_valid():
    geo = Geolocation.from_string("37.5665,126.9780")
    assert geo.latitude  == pytest.approx(37.5665)
    assert geo.longitude == pytest.approx(126.9780)


@pytest.mark.unit
def test_geolocation_parses_negative():
    geo = Geolocation.from_string("-33.8688,151.2093")
    assert geo.latitude < 0


@pytest.mark.unit
def test_geolocation_parses_with_spaces():
    geo = Geolocation.from_string(" 37.5665 , 126.9780 ")
    assert geo.latitude == pytest.approx(37.5665)


@pytest.mark.unit
def test_geolocation_raises_on_invalid():
    with pytest.raises(ValueError):
        Geolocation.from_string("not,valid")


@pytest.mark.unit
def test_geolocation_raises_on_single_value():
    with pytest.raises(ValueError):
        Geolocation.from_string("37.5665")


@pytest.mark.unit
def test_geolocation_is_immutable():
    geo = Geolocation.from_string("37.5665,126.9780")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        geo.latitude = 0.0


# ===========================================================================
# BrowserSettings
# ===========================================================================

@pytest.mark.unit
def test_browser_settings_korean_defaults(monkeypatch):
    monkeypatch.delenv("LOCALE",    raising=False)
    monkeypatch.delenv("TIMEZONE",  raising=False)
    monkeypatch.delenv("LANGUAGE",  raising=False)
    monkeypatch.delenv("USER_AGENT",raising=False)
    monkeypatch.delenv("GEOLOCATION",raising=False)
    monkeypatch.delenv("TIMEZONE_OFFSET_HOURS", raising=False)
    s = _load_browser_settings()
    assert s.locale   == "ko_KR"
    assert s.timezone == "Asia/Seoul"
    assert s.language == "ko"


@pytest.mark.unit
def test_browser_settings_reads_env(monkeypatch):
    monkeypatch.setenv("LOCALE",    "en_US")
    monkeypatch.setenv("TIMEZONE",  "America/New_York")
    monkeypatch.setenv("LANGUAGE",  "en")
    monkeypatch.setenv("GEOLOCATION", "40.7128,-74.0060")
    monkeypatch.setenv("TIMEZONE_OFFSET_HOURS", "-5")
    monkeypatch.setenv("USER_AGENT", "TestAgent/1.0")
    s = _load_browser_settings()
    assert s.locale    == "en_US"
    assert s.timezone  == "America/New_York"
    assert s.user_agent == "TestAgent/1.0"


@pytest.mark.unit
def test_browser_settings_empty_user_agent_is_none(monkeypatch):
    monkeypatch.setenv("USER_AGENT", "")
    s = _load_browser_settings()
    assert s.user_agent is None


@pytest.mark.unit
def test_browser_settings_is_immutable(monkeypatch):
    monkeypatch.delenv("USER_AGENT", raising=False)
    s = _load_browser_settings()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        s.locale = "en_US"
