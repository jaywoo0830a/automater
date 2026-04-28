"""
cli/combo_builder.py
---------------------
Build keyword × title template combinations.

Two keyword shapes are supported:

    Flat::

        keywords:
          region: [강남, 서초]
          subject: [수학, 영어]

        → cartesian product

    Tree (parent → children)::

        keywords:
          region: [강남, 서초]
          district:
            parent: region
            by:
              강남: [대치동, 목동]
              서초: [반포동, 잠원동]
              _default: [전지역]

        → cartesian over flat dimensions, then for each base combo
          tree dimensions are expanded via parent-value lookup.

Combos are 1-indexed for the ``{i}`` DSL token. Trees may nest
(e.g. region → district → dong); validation prevents cycles.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any


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
    keywords: dict[str, Any],
    titles: list[str],
) -> list[Combo]:
    """
    Build all combinations from keywords × titles.

    Each Combo gets a 1-based index for {i} token. Tree keywords are
    expanded after the flat cartesian product, in topological order.
    """
    flat: dict[str, list[str]] = {}
    trees: dict[str, dict] = {}
    declared_order = list(keywords.keys())

    for slug in declared_order:
        value = keywords[slug]
        if isinstance(value, dict):
            trees[slug] = value
        else:
            flat[slug] = value

    # Tree expansion order: a tree must come after its parent.
    tree_order = _topo_order_trees(trees)

    flat_slugs = [s for s in declared_order if s in flat]
    flat_groups = [_deduplicate(flat[s]) for s in flat_slugs]

    if flat_slugs:
        base_combos: list[dict[str, str]] = [
            dict(zip(flat_slugs, vals))
            for vals in itertools.product(*flat_groups)
        ]
    else:
        base_combos = [{}]

    expanded = base_combos
    for slug in tree_order:
        profile = trees[slug]
        parent = profile["parent"]
        by = profile.get("by") or {}
        new_expanded: list[dict[str, str]] = []
        for combo in expanded:
            parent_value = combo.get(parent, "")
            children = by.get(parent_value)
            if children is None:
                children = by.get("_default")
            if not children:
                # Validation should have caught this; skip defensively.
                continue
            for child in _deduplicate(children):
                forked = dict(combo)
                forked[slug] = child
                new_expanded.append(forked)
        expanded = new_expanded

    # Reorder each combo's values to match keywords declaration order so
    # downstream consumers (TitleOption, logs) see a stable layout.
    combos: list[Combo] = []
    counter = 1
    for title_template in titles:
        for values in expanded:
            ordered = {s: values[s] for s in declared_order if s in values}
            combos.append(Combo(
                values=ordered,
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


def _topo_order_trees(trees: dict[str, dict]) -> list[str]:
    """Return tree slugs ordered so each parent precedes its dependents.

    Cycles must already be ruled out by config validation; this helper just
    walks the dependency edges and emits a stable topological order.
    """
    if not trees:
        return []

    visited: set[str] = set()
    out: list[str] = []

    def visit(node: str) -> None:
        if node in visited or node not in trees:
            return
        parent = trees[node].get("parent")
        if isinstance(parent, str):
            visit(parent)
        visited.add(node)
        out.append(node)

    for slug in trees:
        visit(slug)

    return out
