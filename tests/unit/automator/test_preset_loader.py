"""
tests/unit/test_preset_loader.py
-----------------------------------
preset_loader — JSON config → frozen dataclass with compat guarantees.
"""

from automator.preset_loader import load_publish


# ---------------------------------------------------------------------------
# load_publish
# ---------------------------------------------------------------------------

def test_publish_none_returns_defaults():
    """No preset → PublishOption() with all defaults."""
    opt = load_publish(None)
    assert opt.min_tags == 12
    assert opt.visibility == "public"


def test_publish_unknown_keys_ignored():
    """Forward compat: future fields in JSON don't break deserialization."""
    opt = load_publish({"future_field": "v1"})
    assert opt.visibility == "public"


def test_publish_missing_keys_use_defaults():
    """Backward compat: old JSON missing new fields → dataclass defaults."""
    opt = load_publish({"min_tags": 15})
    assert opt.min_tags == 15
    assert opt.visibility == "public"


def test_publish_tags_from_config():
    opt = load_publish({"tags": ["교육", "과외"], "min_tags": 5})
    assert opt.tags == ["교육", "과외"]
    assert opt.min_tags == 5
