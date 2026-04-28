"""
cli/dsl.py
-----------
DSL token interpolation and condition evaluation.

Tokens (usable anywhere — titles, post blocks, image paths):
    {keyword:slug}        → values[slug]
    {pool:slug}           → random choice from pools[slug]
    {map:slug}            → resolved map value
    {i}                   → 1-based combo index
    {variation:name}      → fill the profile template, picking one value
                            from each axis at random
    {variation:name.axis} → random pick from a single axis of the profile

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
    maps: dict[str, str] | None = None,
    variations: dict[str, dict] | None = None,
) -> str:
    """
    Expand DSL tokens in a template string.

    Args:
        template:   String with DSL tokens.
        values:     slug → keyword value mapping.
        pools:      slug → pool value list.
        index:      1-based combo index for {i}.
        rng:        Optional RNG for deterministic pool/variation selection.
                    When provided, the same RNG advances across calls so
                    repeated references to the same profile pick fresh values.
                    When omitted, variation tokens fall back to a per-(index,
                    profile) seeded RNG so the same combo is reproducible
                    across reruns.
        maps:       slug → resolved map value (from map_loader.resolve_maps).
        variations: name → {"axes": {axis: [values...]}, "template": str|None}.
                    Defines composition profiles for {variation:*} tokens.

    Returns:
        Interpolated string.

    Raises:
        KeyError: Referenced slug not found.
    """
    if not template or "{" not in template:
        return template

    pool_rng = rng or random.Random()
    maps = maps or {}
    variations = variations or {}

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
            return pool_rng.choice(pool) if pool else ""

        if token_type == "map":
            if slug in maps:
                return maps[slug]
            return match.group(0)  # unresolved, keep as-is

        if token_type == "variation":
            return _resolve_variation(slug, variations, index, rng)

        return match.group(0)  # unknown type, keep as-is

    return _TOKEN_RE.sub(_replace, template)


def _resolve_variation(
    slug: str,
    variations: dict[str, dict],
    index: int,
    rng: random.Random | None,
) -> str:
    """Resolve a {variation:name} or {variation:name.axis} token.

    With no shared RNG, falls back to ``Random((index, name))`` so the same
    combo always produces the same pick across reruns. Callers that want
    different picks per token reference within one combo must pass a shared
    RNG so its state advances between calls.
    """
    if "." in slug:
        name, axis = slug.split(".", 1)
    else:
        name, axis = slug, None

    if name not in variations:
        raise KeyError(
            f"variation profile '{name}' not found. "
            f"Available: {sorted(variations.keys())}"
        )

    profile = variations[name]
    axes: dict[str, list[str]] = profile.get("axes", {}) or {}
    template: str | None = profile.get("template")

    var_rng = rng if rng is not None else random.Random(f"{index}\x00{name}")

    if axis is not None:
        if axis not in axes:
            raise KeyError(
                f"variation '{name}' has no axis '{axis}'. "
                f"Available axes: {sorted(axes.keys())}"
            )
        items = axes[axis]
        return var_rng.choice(list(items)) if items else ""

    picks: dict[str, str] = {}
    for axis_name, items in axes.items():
        picks[axis_name] = var_rng.choice(list(items)) if items else ""

    if template:
        result = template
        for axis_name, value in picks.items():
            result = result.replace(f"{{{axis_name}}}", value)
        return result

    # Auto-format when no template: prepend a directive block.
    if not picks:
        return ""
    lines = ["", "[작성 지침]"]
    for axis_name, value in picks.items():
        lines.append(f"- {axis_name}: {value}")
    return "\n".join(lines)


def interpolate_deep(
    obj: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    index: int = 0,
    rng: random.Random | None = None,
    maps: dict[str, str] | None = None,
    variations: dict[str, dict] | None = None,
) -> Any:
    """
    Recursively interpolate all string values in a dict/list/scalar.

    Non-string values pass through unchanged.
    """
    if isinstance(obj, str):
        return interpolate(obj, values, pools, index, rng, maps, variations)
    if isinstance(obj, dict):
        return {
            k: interpolate_deep(v, values, pools, index, rng, maps, variations)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [
            interpolate_deep(item, values, pools, index, rng, maps, variations)
            for item in obj
        ]
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
