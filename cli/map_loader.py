"""
cli/map_loader.py
--------------------
Load external YAML map files and resolve keys by keyword values.

Map file format (pure key:value YAML):

    강남: gangnam.jpg
    서초: seocho.jpg
    _default: default.jpg

Campaign YAML reference:

    maps:
      photo:
        file: maps/region_photo.yaml
        by: "{keyword:region}"

DSL token: {map:photo}  → resolved value from file lookup.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_BY_RE = re.compile(r"\{keyword:(\w+)\}")


def load_maps(
    maps_config: dict[str, Any] | None,
    base_dir: str = ".",
) -> dict[str, dict[str, Any]]:
    """
    Load map files from the maps config section.

    Args:
        maps_config: {slug: {file: path, by: "{keyword:slug}"}} from campaign YAML.
        base_dir:    Base directory for resolving relative file paths.

    Returns:
        {slug: {"data": {key: value, ...}, "by": "{keyword:slug}"}}

    Raises:
        FileNotFoundError: If a map file does not exist.
    """
    if not maps_config:
        return {}

    result = {}
    for slug, entry in maps_config.items():
        file_path = entry.get("file", "")
        by = entry.get("by", "")

        path = Path(base_dir) / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Map file not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        result[slug] = {"data": data, "by": by}

    return result


def resolve_maps(
    loaded_maps: dict[str, dict[str, Any]],
    values: dict[str, str],
) -> dict[str, str | list[str]]:
    """
    Resolve all maps to concrete values using the current keyword values.

    For each map:
        1. Extract the keyword slug from the 'by' field
        2. Look up the keyword's current value
        3. Find that value in the map data
        4. Fall back to '_default' if not found

    Values can be:
        str       -> single value (1:1 mapping)
        list[str] -> multiple values (1:N mapping, block expansion)

    Args:
        loaded_maps: Output of load_maps().
        values:      Current combo's keyword values (slug -> value).

    Returns:
        {map_slug: resolved_value} -- ready to pass to interpolate().
    """
    resolved: dict[str, str | list[str]] = {}
    for slug, entry in loaded_maps.items():
        by = entry.get("by", "")
        data = entry.get("data", {})

        # Extract keyword slug from by pattern
        m = _BY_RE.search(by)
        if not m:
            default = data.get("_default", "")
            resolved[slug] = _normalize_value(default)
            continue

        keyword_slug = m.group(1)
        lookup_key = values.get(keyword_slug, "")

        if lookup_key in data:
            resolved[slug] = _normalize_value(data[lookup_key])
        elif "_default" in data:
            resolved[slug] = _normalize_value(data["_default"])
        else:
            resolved[slug] = ""

    return resolved


def _normalize_value(val: Any) -> str | list[str]:
    """맵 값을 str 또는 list[str]로 정규화."""
    if isinstance(val, list):
        return [str(v) for v in val]
    return str(val)
