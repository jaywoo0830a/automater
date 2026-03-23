"""
cli/combo_builder.py
---------------------
Build keyword combinations from CampaignConfig — pure function, no I/O.

Extracts keyword-type token slugs, deduplicates values per category,
then computes the Cartesian product across categories × spacing rules.

    build_keyword_combos(config) → list[KeywordCombo]
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


from cli.campaign_config import CampaignConfig


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeywordCombo:
    """
    One keyword combination — one row of the Cartesian product.

    values:          slug → keyword value (e.g. {"region": "강남", "subject": "수학"})
    spacing_pattern: slug → 0 or 1 (0 = glue to next, 1 = space after)
    """
    values:          dict[str, str]     = field(default_factory=dict)
    spacing_pattern: dict[str, int]     = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_keyword_combos(config: CampaignConfig) -> list[KeywordCombo]:
    """
    Build all keyword combinations from a CampaignConfig.

    Only keyword-type tokens contribute to the Cartesian product.
    Pool and literal tokens are ignored (they affect title generation,
    not combination counting).

    Returns:
        List of KeywordCombo, one per unique (keyword_values, spacing_rule).
    """
    keyword_slugs = _extract_keyword_slugs(config)
    if not keyword_slugs:
        return []

    kw_groups = _build_keyword_groups(keyword_slugs, config.keywords)
    spacing_rules = _resolve_spacing_rules(config)

    return _cartesian_product(keyword_slugs, kw_groups, spacing_rules)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_keyword_slugs(config: CampaignConfig) -> list[str]:
    """Extract slugs of keyword-type tokens in token order."""
    return [
        token.slug
        for token in config.title.tokens
        if token.type == "keyword"
    ]


def _deduplicate(values: list[str]) -> list[str]:
    """Remove duplicates preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        stripped = v.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return result


def _build_keyword_groups(
    slugs: list[str],
    keywords: dict[str, list[str]],
) -> list[list[str]]:
    """Build one deduplicated value list per slug, in slug order."""
    return [_deduplicate(keywords.get(slug, [])) for slug in slugs]


def _resolve_spacing_rules(config: CampaignConfig) -> list[dict[str, int]]:
    """
    Return spacing rules from config, or a single all-spaces default.

    The default rule assigns 1 (space) to every token slug.
    """
    if config.title.spacing_rules:
        return list(config.title.spacing_rules)

    all_slugs = [t.slug for t in config.title.tokens]
    return [{slug: 1 for slug in all_slugs}]


def _cartesian_product(
    slugs: list[str],
    kw_groups: list[list[str]],
    spacing_rules: list[dict[str, int]],
) -> list[KeywordCombo]:
    """Compute Cartesian product of keyword groups × spacing rules."""
    combos: list[KeywordCombo] = []

    for spacing in spacing_rules:
        for combo_values in itertools.product(*kw_groups):
            values = dict(zip(slugs, combo_values))
            combos.append(KeywordCombo(
                values=values,
                spacing_pattern=dict(spacing),
            ))

    return combos
