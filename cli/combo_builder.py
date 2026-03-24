"""
cli/combo_builder.py
---------------------
Build keyword × title template combinations.

    total = ∏(category sizes) × len(titles)

Each Combo holds one set of keyword values and one title template.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Combo:
    """One posting combination: keyword values + title template + index."""
    values:         dict[str, str] = field(default_factory=dict)
    title_template: str            = ""
    index:          int            = 1  # 1-based combo counter


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_combos(
    keywords: dict[str, list[str]],
    titles: list[str],
) -> list[Combo]:
    """
    Build all combinations from keywords × titles.

    Each Combo gets a 1-based index for {i} token.
    """
    slugs = list(keywords.keys())
    groups = [_deduplicate(keywords[slug]) for slug in slugs]

    combos: list[Combo] = []
    counter = 1
    for title_template in titles:
        for combo_values in itertools.product(*groups):
            values = dict(zip(slugs, combo_values))
            combos.append(Combo(
                values=values,
                title_template=title_template,
                index=counter,
            ))
            counter += 1

    return combos


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _deduplicate(values: list[str]) -> list[str]:
    """Strip, remove empties, deduplicate, preserve order."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        stripped = str(v).strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            result.append(stripped)
    return result
