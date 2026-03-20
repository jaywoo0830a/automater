"""
tests/unit/test_preset_loader.py
-----------------------------------
preset_loader — JSON config → frozen dataclass with compat guarantees.
"""

import pytest
from datetime import datetime, timedelta, timezone

from automator.preset_loader import load_publish, load_setting
from automator.options import PublishOption, RunSetting

KST = timezone(timedelta(hours=9))
FUTURE = datetime(2099, 6, 1, 9, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# load_publish
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_publish_none_returns_fixed_default():
    """No preset → fixed-schedule with scheduled_at."""
    opt = load_publish(None, FUTURE)
    assert opt.mode == "fixed"
    assert opt.at == FUTURE


@pytest.mark.unit
def test_publish_config_overrides_mode():
    """Config values override defaults."""
    opt = load_publish({"mode": "random_window", "jitter_minutes": 60}, FUTURE)
    assert opt.mode == "random_window"
    assert opt.jitter_minutes == 60


@pytest.mark.unit
def test_publish_at_always_from_scheduled():
    """Even if config has 'at', it gets overridden by scheduled_at."""
    stale = datetime(2020, 1, 1, tzinfo=KST)
    opt = load_publish({"at": stale.isoformat()}, FUTURE)
    assert opt.at == FUTURE


@pytest.mark.unit
def test_publish_unknown_keys_ignored():
    """Forward compat: future fields in JSON don't break deserialization."""
    opt = load_publish({"future_field": "v1", "mode": "immediate"}, FUTURE)
    assert opt.mode == "immediate"


@pytest.mark.unit
def test_publish_missing_keys_use_defaults():
    """Backward compat: old JSON missing new fields → dataclass defaults."""
    opt = load_publish({"mode": "fixed"}, FUTURE)
    assert opt.min_tags == 12
    assert opt.visibility == "public"


@pytest.mark.unit
def test_publish_tags_from_config():
    opt = load_publish({"tags": ["교육", "과외"], "min_tags": 5}, FUTURE)
    assert opt.tags == ["교육", "과외"]
    assert opt.min_tags == 5


# ---------------------------------------------------------------------------
# load_setting
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_setting_none_returns_defaults():
    """No preset → RunSetting() with all defaults."""
    s = load_setting(None)
    assert s.post_interval == 60
    assert s.headless is True


@pytest.mark.unit
def test_setting_config_overrides():
    s = load_setting({"post_interval": 120, "max_daily_posts": 5})
    assert s.post_interval == 120
    assert s.max_daily_posts == 5


@pytest.mark.unit
def test_setting_unknown_keys_ignored():
    """Forward compat: future fields in JSON don't break deserialization."""
    s = load_setting({"future_setting": True, "headless": False})
    assert s.headless is False


@pytest.mark.unit
def test_setting_missing_keys_use_defaults():
    """Backward compat: partial config → dataclass defaults fill gaps."""
    s = load_setting({"upload_delay_ms": 3000})
    assert s.upload_delay_ms == 3000
    assert s.post_interval == 60
    assert s.on_failure == "stop"
