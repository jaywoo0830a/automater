"""
cli/dsl.py
-----------
DSL token interpolation for arbitrary strings.

Same token syntax as title_generator:
    {keyword:slug}  → values[slug]
    {keywords}      → all values joined in definition order
    {pool:slug}     → random choice from pools[slug]
    plain text      → kept as-is

Used by spec_builder to interpolate post block config strings.
title_generator handles title interpolation directly.
"""

from __future__ import annotations

import random
import re
from typing import Any

_TOKEN_RE = re.compile(r"\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpolate(
    template: str,
    values: dict[str, str],
    pools: dict[str, list[str]],
    rng: random.Random | None = None,
) -> str:
    """
    Expand DSL tokens in a template string.

    Args:
        template: String with {keyword:slug}, {keywords}, {pool:slug} tokens.
        values:   slug → keyword value mapping (definition order preserved).
        pools:    slug → pool value list.
        rng:      Optional RNG for deterministic pool selection.

    Returns:
        Interpolated string.

    Raises:
        KeyError: Referenced slug not found.
    """
    if not template or "{" not in template:
        return template

    rng = rng or random.Random()

    def _replace(match: re.Match) -> str:
        raw = match.group(1)

        if raw == "keywords":
            return " ".join(values.values())

        if ":" not in raw:
            return match.group(0)  # not a DSL token, keep as-is

        token_type, slug = raw.split(":", 1)

        if token_type == "keyword":
            if slug not in values:
                raise KeyError(
                    f"keyword slug '{slug}' not found in values. "
                    f"Available: {sorted(values.keys())}"
                )
            return values[slug]

        if token_type == "pool":
            if slug not in pools:
                raise KeyError(
                    f"pool slug '{slug}' not found in pools. "
                    f"Available: {sorted(pools.keys())}"
                )
            pool = pools[slug]
            return rng.choice(pool) if pool else ""

        return match.group(0)  # unknown type, keep as-is

    return _TOKEN_RE.sub(_replace, template)


def interpolate_deep(
    obj: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    rng: random.Random | None = None,
) -> Any:
    """
    Recursively interpolate all string values in a dict/list/scalar.

    Non-string values pass through unchanged.
    """
    if isinstance(obj, str):
        return interpolate(obj, values, pools, rng)
    if isinstance(obj, dict):
        return {k: interpolate_deep(v, values, pools, rng) for k, v in obj.items()}
    if isinstance(obj, list):
        return [interpolate_deep(item, values, pools, rng) for item in obj]
    return obj
