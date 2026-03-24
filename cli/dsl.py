"""
cli/dsl.py
-----------
DSL token interpolation and condition evaluation.

Tokens (usable anywhere — titles, post blocks, image paths):
    {keyword:slug}  → values[slug]
    {pool:slug}     → random choice from pools[slug]
    {i}             → 1-based combo index

Conditions (used in post block `when` clauses):
    {keyword:slug} == value
    {keyword:slug} != value
    {keyword:slug} in [value1, value2, ...]
    {keyword:slug} not in [value1, value2, ...]
"""

from __future__ import annotations

import random
import re
from typing import Any

_TOKEN_RE = re.compile(r"\{([^}]+)\}")

_COND_EQ_RE = re.compile(
    r"\{keyword:(\w+)\}\s*==\s*(.+)"
)
_COND_NEQ_RE = re.compile(
    r"\{keyword:(\w+)\}\s*!=\s*(.+)"
)
_COND_IN_RE = re.compile(
    r"\{keyword:(\w+)\}\s+in\s+\[([^\]]*)\]"
)
_COND_NOT_IN_RE = re.compile(
    r"\{keyword:(\w+)\}\s+not\s+in\s+\[([^\]]*)\]"
)


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------

def interpolate(
    template: str,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int = 0,
    rng: random.Random | None = None,
) -> str:
    """
    Expand DSL tokens in a template string.

    Args:
        template: String with {keyword:slug}, {pool:slug}, {i} tokens.
        values:   slug → keyword value mapping.
        pools:    slug → pool value list.
        index:    1-based combo index for {i}.
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

        # {i} — combo index
        if raw == "i":
            return str(index)

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
    index: int = 0,
    rng: random.Random | None = None,
) -> Any:
    """
    Recursively interpolate all string values in a dict/list/scalar.

    Non-string values pass through unchanged.
    """
    if isinstance(obj, str):
        return interpolate(obj, values, pools, index, rng)
    if isinstance(obj, dict):
        return {k: interpolate_deep(v, values, pools, index, rng) for k, v in obj.items()}
    if isinstance(obj, list):
        return [interpolate_deep(item, values, pools, index, rng) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

def evaluate_condition(
    condition: str,
    values: dict[str, str],
) -> bool:
    """
    Evaluate a when-condition string against keyword values.

    Supported forms:
        {keyword:slug} == value
        {keyword:slug} != value
        {keyword:slug} in [value1, value2, ...]
        {keyword:slug} not in [value1, value2, ...]

    Returns True if the condition passes (block should be included).
    Returns True for empty/None conditions.

    Raises:
        ValueError: Unparseable condition syntax.
        KeyError: Referenced slug not in values.
    """
    if not condition or not condition.strip():
        return True

    cond = condition.strip()

    # not in (must check before 'in' to avoid false match)
    m = _COND_NOT_IN_RE.match(cond)
    if m:
        slug, items_str = m.group(1), m.group(2)
        actual = _resolve_slug(slug, values)
        items = _parse_list_values(items_str)
        return actual not in items

    # in
    m = _COND_IN_RE.match(cond)
    if m:
        slug, items_str = m.group(1), m.group(2)
        actual = _resolve_slug(slug, values)
        items = _parse_list_values(items_str)
        return actual in items

    # !=
    m = _COND_NEQ_RE.match(cond)
    if m:
        slug, expected = m.group(1), m.group(2).strip()
        actual = _resolve_slug(slug, values)
        return actual != expected

    # ==
    m = _COND_EQ_RE.match(cond)
    if m:
        slug, expected = m.group(1), m.group(2).strip()
        actual = _resolve_slug(slug, values)
        return actual == expected

    raise ValueError(f"Unparseable when-condition: {cond!r}")


def _resolve_slug(slug: str, values: dict[str, str]) -> str:
    """Resolve a keyword slug to its value."""
    if slug not in values:
        raise KeyError(
            f"Condition references unknown keyword '{slug}'. "
            f"Available: {sorted(values.keys())}"
        )
    return values[slug]


def _parse_list_values(raw: str) -> list[str]:
    """Parse comma-separated values from inside [...] brackets."""
    return [v.strip() for v in raw.split(",") if v.strip()]
