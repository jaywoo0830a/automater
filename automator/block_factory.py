"""
automator/block_factory.py
----------------------------
BlockFactory — block_type string → Block dataclass.

Used by SpecBuilder to convert LayoutSlot rows into Block instances.
Placeholder interpolation replaces {keyword}, {region}, etc. in config
values with actual combination keyword values.

Adding a new block type:
    1. Define the Block dataclass in options.py
    2. Add one entry to FACTORIES dict

Usage:
    values  = {"region": "강남", "subject": "수학"}
    keyword = "강남 수학"
    config  = {"keyword": "{keyword}", "tone": "review"}

    block = BlockFactory.create("paragraph", config, values, keyword)
    # → ParagraphBlock(keyword="강남 수학", tone="review")
"""

from __future__ import annotations

import re
from dataclasses import fields as dc_fields
from typing import Any

from automator.options import (
    Block,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
)


# ---------------------------------------------------------------------------
# Registry — block_type string → Block class
# ---------------------------------------------------------------------------

FACTORIES: dict[str, type] = {
    "paragraph": ParagraphBlock,
    "image":     ImageBlock,
    "featured":  FeaturedImageBlock,
    "heading":   HeadingBlock,
    "list":      ListBlock,
    "quote":     QuoteBlock,
    "divider":   DividerBlock,
}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_block(
    block_type: str,
    config: dict[str, Any],
    values: dict[str, str] | None = None,
    keyword: str = "",
) -> Block:
    """
    Create a Block dataclass from a block_type string and config dict.

    Args:
        block_type: Registry key ("paragraph", "image", etc.)
        config:     LayoutSlot.config JSON — may contain {keyword}, {region} etc.
        values:     Combination keyword slug→value map for interpolation.
        keyword:    Full keyword string (all values joined with space).

    Returns:
        Frozen Block dataclass instance.

    Raises:
        KeyError: block_type not in FACTORIES.
        TypeError: config key not accepted by the Block dataclass.
    """
    if block_type not in FACTORIES:
        raise KeyError(
            f"Unknown block_type: {block_type!r}. "
            f"Registered: {sorted(FACTORIES.keys())}"
        )

    cls = FACTORIES[block_type]
    interpolated = _interpolate(config, values or {}, keyword)
    filtered = _filter_fields(cls, interpolated)
    return cls(**filtered)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _interpolate(
    config: dict[str, Any],
    values: dict[str, str],
    keyword: str,
) -> dict[str, Any]:
    """
    Replace {placeholders} in string values of config dict.

    Supported placeholders:
        {keyword}   — full keyword string ("강남 수학 과외")
        {slug_name} — individual keyword value by category slug
    """
    lookup = {**values, "keyword": keyword}
    result: dict[str, Any] = {}
    for k, v in config.items():
        if isinstance(v, str):
            result[k] = _PLACEHOLDER_RE.sub(
                lambda m: lookup.get(m.group(1), m.group(0)), v
            )
        elif isinstance(v, list):
            result[k] = [
                _PLACEHOLDER_RE.sub(
                    lambda m: lookup.get(m.group(1), m.group(0)), item
                ) if isinstance(item, str) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def _filter_fields(cls: type, config: dict[str, Any]) -> dict[str, Any]:
    """Keep only keys that match dataclass field names. Ignore unknown keys."""
    valid = {f.name for f in dc_fields(cls)}
    return {k: v for k, v in config.items() if k in valid}
