"""
tests/unit/cli/test_combo_builder.py
--------------------------------------
combo_builder — keywords × spacing_rules → KeywordCombo list.

Tests cover:
    - Cartesian product correctness
    - Single category, multiple categories
    - Multiple spacing rules
    - Empty inputs
    - Deduplication of keyword values
"""

from __future__ import annotations

import pytest

from cli.campaign_config import CampaignConfig, TitleConfig, TokenEntry
from cli.combo_builder import build_keyword_combos, KeywordCombo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugs(combo: KeywordCombo) -> tuple[str, ...]:
    """Extract sorted slug values for easy comparison."""
    return tuple(combo.values[k] for k in sorted(combo.values.keys()))


# ---------------------------------------------------------------------------
# Single category, single spacing rule
# ---------------------------------------------------------------------------

class TestSingleCategory:

    def test_three_keywords_produce_three_combos(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="region", type="keyword"),),
                spacing_rules=({"region": 1},),
            ),
            keywords={"region": ["강남", "서초", "잠실"]},
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 3

    def test_combo_values_match_keywords(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="region", type="keyword"),),
                spacing_rules=({"region": 1},),
            ),
            keywords={"region": ["강남", "서초"]},
        )
        combos = build_keyword_combos(config)
        values = {c.values["region"] for c in combos}
        assert values == {"강남", "서초"}

    def test_spacing_pattern_attached(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="region", type="keyword"),),
                spacing_rules=({"region": 0},),
            ),
            keywords={"region": ["강남"]},
        )
        combos = build_keyword_combos(config)
        assert combos[0].spacing_pattern == {"region": 0}


# ---------------------------------------------------------------------------
# Multiple categories — Cartesian product
# ---------------------------------------------------------------------------

class TestMultipleCategories:

    def test_two_categories_produce_cartesian_product(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(
                    TokenEntry(slug="region", type="keyword"),
                    TokenEntry(slug="subject", type="keyword"),
                ),
                spacing_rules=({"region": 1, "subject": 1},),
            ),
            keywords={
                "region": ["강남", "서초"],
                "subject": ["수학", "영어"],
            },
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 4  # 2 × 2

    def test_three_categories_produce_full_product(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(
                    TokenEntry(slug="a", type="keyword"),
                    TokenEntry(slug="b", type="keyword"),
                    TokenEntry(slug="c", type="keyword"),
                ),
                spacing_rules=({"a": 1, "b": 1, "c": 1},),
            ),
            keywords={"a": ["1", "2"], "b": ["x", "y"], "c": ["α"]},
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 4  # 2 × 2 × 1

    def test_combo_values_are_correct_pairs(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(
                    TokenEntry(slug="region", type="keyword"),
                    TokenEntry(slug="subject", type="keyword"),
                ),
                spacing_rules=({"region": 1, "subject": 1},),
            ),
            keywords={"region": ["A", "B"], "subject": ["X"]},
        )
        combos = build_keyword_combos(config)
        pairs = {(c.values["region"], c.values["subject"]) for c in combos}
        assert pairs == {("A", "X"), ("B", "X")}


# ---------------------------------------------------------------------------
# Multiple spacing rules
# ---------------------------------------------------------------------------

class TestMultipleSpacingRules:

    def test_spacing_rules_multiply_combos(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="region", type="keyword"),),
                spacing_rules=(
                    {"region": 1},
                    {"region": 0},
                ),
            ),
            keywords={"region": ["강남", "서초"]},
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 4  # 2 keywords × 2 spacing rules

    def test_each_combo_has_its_spacing_pattern(self):
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="r", type="keyword"),),
                spacing_rules=({"r": 1}, {"r": 0}),
            ),
            keywords={"r": ["A"]},
        )
        combos = build_keyword_combos(config)
        patterns = {tuple(sorted(c.spacing_pattern.items())) for c in combos}
        assert len(patterns) == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_no_spacing_rules_uses_default(self):
        """When spacing_rules is empty, use a single all-spaces default."""
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="r", type="keyword"),),
                spacing_rules=(),
            ),
            keywords={"r": ["A"]},
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 1
        # Default: all slugs get space (1)
        assert combos[0].spacing_pattern["r"] == 1

    def test_pool_and_literal_tokens_ignored_in_keyword_groups(self):
        """Only keyword-type tokens define the Cartesian product axes."""
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(
                    TokenEntry(slug="salt", type="pool"),
                    TokenEntry(slug="region", type="keyword"),
                    TokenEntry(slug="과외", type="literal", value="과외"),
                ),
                spacing_rules=({"salt": 1, "region": 1, "과외": 1},),
            ),
            keywords={"region": ["A", "B"]},
            palettes={"salt": ["X"]},
        )
        combos = build_keyword_combos(config)
        # Only 'region' contributes to combos: 2 keywords × 1 rule = 2
        assert len(combos) == 2
        assert "region" in combos[0].values
        assert "salt" not in combos[0].values

    def test_duplicate_keywords_deduplicated(self):
        """Duplicate keyword values within a category are removed."""
        config = CampaignConfig(
            title=TitleConfig(
                tokens=(TokenEntry(slug="r", type="keyword"),),
                spacing_rules=({"r": 1},),
            ),
            keywords={"r": ["A", "B", "A", "B", "C"]},
        )
        combos = build_keyword_combos(config)
        assert len(combos) == 3  # A, B, C (deduplicated)
