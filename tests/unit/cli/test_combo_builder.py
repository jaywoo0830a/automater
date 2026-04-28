"""
tests/unit/cli/test_combo_builder.py
--------------------------------------
Keyword × title template combinations.
"""

import pytest

from cli.combo_builder import build_combos, Combo


# ---------------------------------------------------------------------------
# Basic product
# ---------------------------------------------------------------------------

class TestBasicProduct:

    def test_single_category_single_title(self):
        combos = build_combos(
            keywords={"region": ["강남", "서초"]},
            titles=["{keyword:region}"],
        )
        assert len(combos) == 2

    def test_two_categories(self):
        combos = build_combos(
            keywords={"region": ["강남", "서초"], "subject": ["수학", "영어"]},
            titles=["{keyword:region}"],
        )
        assert len(combos) == 4  # 2 × 2

    def test_three_categories(self):
        combos = build_combos(
            keywords={"a": ["1", "2"], "b": ["x"], "c": ["α", "β"]},
            titles=["{keyword:region}"],
        )
        assert len(combos) == 4  # 2 × 1 × 2

    def test_values_correct(self):
        combos = build_combos(
            keywords={"region": ["A", "B"], "subject": ["X"]},
            titles=["{keyword:region}"],
        )
        pairs = {(c.values["region"], c.values["subject"]) for c in combos}
        assert pairs == {("A", "X"), ("B", "X")}


# ---------------------------------------------------------------------------
# Multiple titles multiply combos
# ---------------------------------------------------------------------------

class TestMultipleTitles:

    def test_two_titles_double_combos(self):
        combos = build_combos(
            keywords={"region": ["강남", "서초"]},
            titles=["template_1", "template_2"],
        )
        assert len(combos) == 4  # 2 keywords × 2 titles

    def test_each_combo_has_its_template(self):
        combos = build_combos(
            keywords={"r": ["A"]},
            titles=["T1", "T2", "T3"],
        )
        templates = {c.title_template for c in combos}
        assert templates == {"T1", "T2", "T3"}

    def test_combo_count_formula(self):
        """total = ∏(category sizes) × len(titles)"""
        combos = build_combos(
            keywords={"a": ["1", "2", "3"], "b": ["x", "y"]},
            titles=["T1", "T2"],
        )
        assert len(combos) == 3 * 2 * 2  # 12


# ---------------------------------------------------------------------------
# Combo fields
# ---------------------------------------------------------------------------

class TestComboFields:

    def test_combo_has_values(self):
        combos = build_combos(
            keywords={"region": ["강남"]},
            titles=["T"],
        )
        assert combos[0].values == {"region": "강남"}

    def test_combo_has_title_template(self):
        combos = build_combos(
            keywords={"region": ["강남"]},
            titles=["T"],
        )
        assert combos[0].title_template == "T"

    def test_combo_has_1_based_index(self):
        combos = build_combos(
            keywords={"region": ["A", "B", "C"]},
            titles=["T"],
        )
        assert combos[0].index == 1
        assert combos[1].index == 2
        assert combos[2].index == 3

    def test_index_continuous_across_titles(self):
        combos = build_combos(
            keywords={"r": ["A", "B"]},
            titles=["T1", "T2"],
        )
        indices = [c.index for c in combos]
        assert indices == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_deduplicates_keywords(self):
        combos = build_combos(
            keywords={"r": ["A", "B", "A"]},
            titles=["T"],
        )
        assert len(combos) == 2  # A, B

    def test_strips_whitespace(self):
        combos = build_combos(
            keywords={"r": ["  A  ", "B"]},
            titles=["T"],
        )
        values = {c.values["r"] for c in combos}
        assert values == {"A", "B"}


# ---------------------------------------------------------------------------
# Tree keywords (parent → children)
# ---------------------------------------------------------------------------

class TestTreeKeywords:

    def test_single_level_tree(self):
        combos = build_combos(
            keywords={
                "region": ["강남", "서초"],
                "district": {
                    "parent": "region",
                    "by": {
                        "강남": ["대치동", "목동"],
                        "서초": ["반포동"],
                    },
                },
            },
            titles=["T"],
        )
        pairs = {(c.values["region"], c.values["district"]) for c in combos}
        assert pairs == {
            ("강남", "대치동"), ("강남", "목동"), ("서초", "반포동"),
        }

    def test_tree_combined_with_other_flat_dim(self):
        combos = build_combos(
            keywords={
                "region": ["강남", "서초"],
                "district": {
                    "parent": "region",
                    "by": {
                        "강남": ["대치동", "목동"],
                        "서초": ["반포동", "잠원동"],
                    },
                },
                "subject": ["수학"],
            },
            titles=["T"],
        )
        # 2 regions × children-per-region × 1 subject = 2+2 = 4
        assert len(combos) == 4
        for c in combos:
            assert c.values["subject"] == "수학"

    def test_default_fallback(self):
        combos = build_combos(
            keywords={
                "region": ["강남", "서초", "송파"],
                "district": {
                    "parent": "region",
                    "by": {
                        "강남": ["대치동"],
                        "_default": ["전지역"],
                    },
                },
            },
            titles=["T"],
        )
        pairs = {(c.values["region"], c.values["district"]) for c in combos}
        assert pairs == {
            ("강남", "대치동"),
            ("서초", "전지역"),
            ("송파", "전지역"),
        }

    def test_multi_level_tree(self):
        combos = build_combos(
            keywords={
                "region": ["강남"],
                "district": {
                    "parent": "region",
                    "by": {"강남": ["대치동", "목동"]},
                },
                "dong": {
                    "parent": "district",
                    "by": {
                        "대치동": ["은마", "선경"],
                        "목동": ["1단지"],
                    },
                },
            },
            titles=["T"],
        )
        triples = {
            (c.values["region"], c.values["district"], c.values["dong"])
            for c in combos
        }
        assert triples == {
            ("강남", "대치동", "은마"),
            ("강남", "대치동", "선경"),
            ("강남", "목동", "1단지"),
        }

    def test_tree_declared_before_parent_still_works(self):
        # Declaration order shouldn't matter — topo sort handles it.
        combos = build_combos(
            keywords={
                "district": {
                    "parent": "region",
                    "by": {"강남": ["대치동", "목동"]},
                },
                "region": ["강남"],
            },
            titles=["T"],
        )
        pairs = {(c.values["region"], c.values["district"]) for c in combos}
        assert pairs == {("강남", "대치동"), ("강남", "목동")}

    def test_combo_values_in_declaration_order(self):
        combos = build_combos(
            keywords={
                "region": ["강남"],
                "district": {
                    "parent": "region",
                    "by": {"강남": ["대치동"]},
                },
                "subject": ["수학"],
            },
            titles=["T"],
        )
        keys = list(combos[0].values.keys())
        assert keys == ["region", "district", "subject"]

    def test_tree_dedupes_children(self):
        combos = build_combos(
            keywords={
                "region": ["강남"],
                "district": {
                    "parent": "region",
                    "by": {"강남": ["대치동", "대치동", "  대치동  ", "목동"]},
                },
            },
            titles=["T"],
        )
        assert len(combos) == 2

    def test_index_continuous_with_tree(self):
        combos = build_combos(
            keywords={
                "region": ["강남", "서초"],
                "district": {
                    "parent": "region",
                    "by": {
                        "강남": ["대치동", "목동"],
                        "서초": ["반포동"],
                    },
                },
            },
            titles=["T"],
        )
        assert [c.index for c in combos] == [1, 2, 3]
