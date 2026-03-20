"""
tests/test_config.py
--------------------
Unit tests for BrowserSettings and Geolocation (automator/config.py).

AccountOption 테스트는 test_job_builder.py 에 있다.
"""

import pytest
from dataclasses import FrozenInstanceError

from automator.config import Geolocation, _load_browser_settings


# ===========================================================================
# Geolocation.from_string
# ===========================================================================

def test_geolocation_parses_valid():
    geo = Geolocation.from_string("37.5665,126.9780")
    assert geo.latitude  == pytest.approx(37.5665)
    assert geo.longitude == pytest.approx(126.9780)


def test_geolocation_parses_negative():
    geo = Geolocation.from_string("-33.8688,151.2093")
    assert geo.latitude < 0


def test_geolocation_parses_with_spaces():
    geo = Geolocation.from_string(" 37.5665 , 126.9780 ")
    assert geo.latitude == pytest.approx(37.5665)


def test_geolocation_raises_on_invalid():
    with pytest.raises(ValueError):
        Geolocation.from_string("not,valid")


def test_geolocation_raises_on_single_value():
    with pytest.raises(ValueError):
        Geolocation.from_string("37.5665")


# ===========================================================================
# BrowserSettings
# ===========================================================================

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


def test_browser_settings_empty_user_agent_is_none(monkeypatch):
    monkeypatch.setenv("USER_AGENT", "")
    s = _load_browser_settings()
    assert s.user_agent is None


# ===========================================================================
# get_app_env / is_production (ENV 환경변수 기반)
# ===========================================================================

def test_get_app_env_returns_test(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    from automator.config import get_app_env
    assert get_app_env() == "test"


def test_get_app_env_returns_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    from automator.config import get_app_env
    assert get_app_env() == "dev"


def test_get_app_env_returns_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    from automator.config import get_app_env
    assert get_app_env() == "production"


def test_get_app_env_defaults_to_dev_when_unset(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    from automator.config import get_app_env
    assert get_app_env() == "dev"


def test_get_app_env_unknown_value_warns_and_falls_back(monkeypatch):
    import warnings
    monkeypatch.setenv("ENV", "staging")
    from automator.config import get_app_env
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_app_env()
    assert result == "dev"
    assert any("Unknown ENV" in str(x.message) for x in w)


def test_is_production_false_for_test(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    from automator.config import is_production
    assert is_production() is False


def test_is_production_false_for_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    from automator.config import is_production
    assert is_production() is False


def test_is_production_true_for_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    from automator.config import is_production
    assert is_production() is True
