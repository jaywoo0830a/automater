"""
automator/preset_loader.py
-----------------------------
Deserialize JSON config dicts into frozen dataclass instances.

Forward compatible: unknown keys in config are silently ignored.
Backward compatible: missing keys fall back to dataclass defaults.

Usage:
    from automator.preset_loader import load_publish

    publish_opt = load_publish(preset_config_dict)
"""

from __future__ import annotations

from dataclasses import fields as dc_fields
from typing import Any

from automator.options import PublishOption


def _deserialize(cls: type, config: dict[str, Any]) -> Any:
    """
    Create a frozen dataclass from a JSON config dict.

    - Keys present in config but absent in cls fields → ignored.
    - Keys absent in config but present in cls fields → use default.
    """
    valid = {f.name for f in dc_fields(cls)}
    filtered = {k: v for k, v in config.items() if k in valid}
    return cls(**filtered)


def load_publish(
    config: dict[str, Any] | None,
) -> PublishOption:
    """
    Build a PublishOption from preset config JSON.

    If config is None (no preset), returns PublishOption() with all defaults.
    """
    if config is None:
        return PublishOption()
    return _deserialize(PublishOption, config)
