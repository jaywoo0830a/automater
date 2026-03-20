"""
automator/block_factory.py
----------------------------
BlockFactory — block_type string → Block dataclass.

Used by SpecBuilder to convert LayoutSlot rows into Block instances.
Placeholder interpolation replaces {keyword}, {region}, etc. in config
values with actual combination keyword values.

media_id resolution: if config contains "media_id" and a media_resolver
is provided, the resolver translates media_id → absolute filesystem path
and injects it as "path" into the config.

Adding a new block type:
    1. Define the Block dataclass in options.py
    2. Add one entry to FACTORIES dict
"""

from __future__ import annotations

import re
from dataclasses import fields as dc_fields
from typing import Any, Callable

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

_MEDIA_BLOCK_TYPES = {"image", "featured"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_block(
    block_type: str,
    config: dict[str, Any],
    values: dict[str, str] | None = None,
    keyword: str = "",
    media_resolver: Callable[[int], str] | None = None,
) -> Block:
    """
    Create a Block dataclass from a block_type string and config dict.

    Args:
        block_type:     Registry key ("paragraph", "image", etc.)
        config:         LayoutSlot.config JSON — may contain {keyword}, {region},
                        and media_id for image/featured blocks.
        values:         Combination keyword slug→value map for interpolation.
        keyword:        Full keyword string (all values joined with space).
        media_resolver: Callable that takes media_id (int) and returns absolute
                        file path (str). Required when config has media_id.

    Returns:
        Frozen Block dataclass instance.

    Raises:
        KeyError:   block_type not in FACTORIES.
        ValueError: media_id present but no media_resolver provided.
    """
    if block_type not in FACTORIES:
        raise KeyError(
            f"Unknown block_type: {block_type!r}. "
            f"Registered: {sorted(FACTORIES.keys())}"
        )

    cls = FACTORIES[block_type]
    working = dict(config)

    working = _resolve_media(working, block_type, media_resolver)
    working = _interpolate(working, values or {}, keyword)
    filtered = _filter_fields(cls, working)
    return cls(**filtered)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_media(
    config: dict[str, Any],
    block_type: str,
    resolver: Callable[[int], str] | None,
) -> dict[str, Any]:
    """
    If config has media_id and no explicit path, resolve media_id → path.

    Explicit path always takes precedence over media_id.
    Non-image blocks silently ignore media_id via _filter_fields later.
    """
    if "media_id" not in config:
        return config

    if block_type in _MEDIA_BLOCK_TYPES and "path" not in config:
        if resolver is None:
            raise ValueError(
                f"Config has media_id={config['media_id']} but no "
                f"media_resolver was provided. Pass a resolver or "
                f"use an explicit 'path' instead."
            )
        resolved_path = resolver(config["media_id"])
        config = {**config, "path": resolved_path}

    config.pop("media_id", None)
    return config


def _interpolate(
    config: dict[str, Any],
    values: dict[str, str],
    keyword: str,
) -> dict[str, Any]:
    """
    Replace {placeholders} in string values of config dict.

    Supported placeholders:
        {keyword}   — full keyword string
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
