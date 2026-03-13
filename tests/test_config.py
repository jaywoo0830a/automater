"""
tests/test_config.py
--------------------
Unit tests for automator.config (BrowserSettings) and AccountOption.

config.py: 브라우저 로컬라이제이션만 담당.
AccountOption: 계정 정보 담당 (options.py).
"""

import pytest
from dataclasses import FrozenInstanceError, replace

from automator.config import Geolocation, BrowserSettings, _load_browser_settings
from automator.options import AccountOption


# ---------------------------------------------------------------------------
# Geolocation.from_string
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_geolocation_parses_seoul():
    geo = Geolocation.from_string("37.5665,126.9780")
    assert geo.latitude == 37.5665 and geo.longitude == 126.9780


@pytest.mark.unit
def test_geolocation_parses_negative_longitude():
    geo = Geolocation.from_string("40.7128,-74.0060")
    assert geo.longitude == -74.0060


@pytest.mark.unit
def test_geolocation_parses_with_spaces():
    geo = Geolocation.from_string("35.6762, 139.6503")
    assert geo.latitude == 35.6762 and geo.longitude == 139.6503


@pytest.mark.unit
def test_geolocation_raises_on_invalid_format():
    with pytest.raises(ValueError, match="GEOLOCATION must be"):
        Geolocation.from_string("not_a_coordinate")


@pytest.mark.unit
def test_geolocation_raises_on_single_value():
    with pytest.raises(ValueError):
        Geolocation.from_string("37.5665")


@pytest.mark.unit
def test_geolocation_is_immutable():
    geo = Geolocation(latitude=37.5665, longitude=126.9780)
    with pytest.raises((FrozenInstanceError, TypeError)):
        geo.latitude = 0.0  # type: ignore


# ---------------------------------------------------------------------------
# _load_browser_settings
# ---------------------------------------------------------------------------

MOCK_ENV = {
    "LOCALE":                "en_US",
    "TIMEZONE":              "America/New_York",
    "LANGUAGE":              "en",
    "GEOLOCATION":           "40.7128,-74.0060",
    "TIMEZONE_OFFSET_HOURS": "-5",
    "USER_AGENT":            "Mozilla/5.0 TestAgent",
}


@pytest.mark.unit
def test_browser_settings_loads_locale(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    assert _load_browser_settings().locale == "en_US"


@pytest.mark.unit
def test_browser_settings_loads_timezone(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    assert _load_browser_settings().timezone == "America/New_York"


@pytest.mark.unit
def test_browser_settings_loads_language(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    assert _load_browser_settings().language == "en"


@pytest.mark.unit
def test_browser_settings_loads_geolocation(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    s = _load_browser_settings()
    assert s.geolocation.latitude == 40.7128 and s.geolocation.longitude == -74.0060


@pytest.mark.unit
def test_browser_settings_loads_timezone_offset(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    assert _load_browser_settings().timezone_offset_hours == -5


@pytest.mark.unit
def test_browser_settings_loads_user_agent(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    assert _load_browser_settings().user_agent == "Mozilla/5.0 TestAgent"


@pytest.mark.unit
def test_browser_settings_empty_user_agent_becomes_none(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    monkeypatch.setenv("USER_AGENT", "")
    assert _load_browser_settings().user_agent is None


@pytest.mark.unit
def test_browser_settings_korean_defaults(monkeypatch):
    for key in MOCK_ENV: monkeypatch.delenv(key, raising=False)
    s = _load_browser_settings()
    assert s.locale == "ko_KR"
    assert s.timezone == "Asia/Seoul"
    assert s.language == "ko"
    assert s.timezone_offset_hours == 9
    assert s.geolocation.latitude == 37.5665


@pytest.mark.unit
def test_browser_settings_is_immutable(monkeypatch):
    for k, v in MOCK_ENV.items(): monkeypatch.setenv(k, v)
    s = _load_browser_settings()
    with pytest.raises((FrozenInstanceError, TypeError)):
        s.locale = "zh_CN"  # type: ignore


# ---------------------------------------------------------------------------
# AccountOption
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_account_write_url():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="rlawjddn00az")
    assert acc.write_url == "https://blog.naver.com/rlawjddn00az?Redirect=Write&"


@pytest.mark.unit
def test_account_write_url_contains_redirect_param():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    assert "Redirect=Write" in acc.write_url


@pytest.mark.unit
def test_account_resolved_session_path_default():
    acc = AccountOption(naver_id="myid", naver_pw="pw", blog_id="blog")
    assert acc.resolved_session_path == "myid_session.json"


@pytest.mark.unit
def test_account_resolved_session_path_custom():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog", session_path="custom.json")
    assert acc.resolved_session_path == "custom.json"


@pytest.mark.unit
def test_account_is_immutable():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    with pytest.raises((FrozenInstanceError, TypeError)):
        acc.naver_id = "hacked"  # type: ignore


@pytest.mark.unit
def test_account_post_count_default():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    assert acc.post_count == 1


@pytest.mark.unit
def test_account_proxies_default_empty():
    acc = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    assert acc.proxies == []


@pytest.mark.unit
def test_account_replace_produces_new_instance():
    acc  = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    acc2 = replace(acc, blog_id="other")
    assert acc.blog_id == "blog" and acc2.blog_id == "other"
