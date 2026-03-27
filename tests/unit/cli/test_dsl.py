"""
tests/unit/cli/test_dsl.py
----------------------------
DSL token interpolation and condition evaluation.

Tokens: {keyword:slug}, {pool:slug}, {i}
Conditions: ==, !=, in [...], not in [...]
"""

import random
import pytest

from cli.dsl import interpolate, interpolate_deep, evaluate_condition


# ---------------------------------------------------------------------------
# {keyword:slug}
# ---------------------------------------------------------------------------

class TestKeywordToken:

    def test_single(self):
        assert interpolate("{keyword:region} 소개", {"region": "강남"}, {}) == "강남 소개"

    def test_multiple(self):
        result = interpolate(
            "{keyword:region} {keyword:subject}",
            {"region": "강남", "subject": "수학"}, {},
        )
        assert result == "강남 수학"

    def test_glued(self):
        result = interpolate(
            "{keyword:region}{keyword:subject}과외",
            {"region": "강남", "subject": "수학"}, {},
        )
        assert result == "강남수학과외"

    def test_missing_raises(self):
        with pytest.raises(KeyError, match="missing"):
            interpolate("{keyword:missing}", {}, {})


# ---------------------------------------------------------------------------
# {pool:slug}
# ---------------------------------------------------------------------------

class TestPoolToken:

    def test_selects_from_list(self):
        result = interpolate("{pool:p}", {}, {"p": ["A", "B"]}, rng=random.Random(42))
        assert result in ("A", "B")

    def test_missing_raises(self):
        with pytest.raises(KeyError, match="missing"):
            interpolate("{pool:missing}", {}, {})

    def test_empty_returns_empty(self):
        assert interpolate("{pool:e}", {}, {"e": []}) == ""

    def test_deterministic_with_seed(self):
        r1 = interpolate("{pool:p}", {}, {"p": ["A", "B"]}, rng=random.Random(42))
        r2 = interpolate("{pool:p}", {}, {"p": ["A", "B"]}, rng=random.Random(42))
        assert r1 == r2


# ---------------------------------------------------------------------------
# {i} — combo index
# ---------------------------------------------------------------------------

class TestIndexToken:

    def test_basic(self):
        assert interpolate("{i}.jpg", {}, {}, index=3) == "3.jpg"

    def test_in_path(self):
        assert interpolate("images/{i}.jpg", {}, {}, index=1) == "images/1.jpg"

    def test_mixed_with_keywords(self):
        result = interpolate(
            "{keyword:region}_{i}.jpg",
            {"region": "강남"}, {},
            index=5,
        )
        assert result == "강남_5.jpg"

    def test_default_index_zero(self):
        assert interpolate("{i}", {}, {}) == "0"

    def test_in_text(self):
        result = interpolate("포스팅 #{i}", {}, {}, index=12)
        assert result == "포스팅 #12"


# ---------------------------------------------------------------------------
# Mixed / Literals
# ---------------------------------------------------------------------------

class TestMixed:

    def test_all_token_types(self):
        result = interpolate(
            "{pool:prefix} {keyword:region} {keyword:subject} #{i}",
            {"region": "강남", "subject": "수학"},
            {"prefix": ["검증된"]},
            index=7,
        )
        assert result == "검증된 강남 수학 #7"

    def test_no_tokens(self):
        assert interpolate("리터럴 텍스트만", {}, {}) == "리터럴 텍스트만"

    def test_empty_string(self):
        assert interpolate("", {}, {}) == ""


# ---------------------------------------------------------------------------
# interpolate_deep
# ---------------------------------------------------------------------------

class TestInterpolateDeep:

    def test_dict(self):
        data = {"text": "{keyword:r} 소개", "level": 2}
        result = interpolate_deep(data, {"r": "강남"}, {})
        assert result == {"text": "강남 소개", "level": 2}

    def test_nested(self):
        data = {"outer": {"inner": "{keyword:r}"}}
        result = interpolate_deep(data, {"r": "강남"}, {})
        assert result == {"outer": {"inner": "강남"}}

    def test_list(self):
        data = ["{keyword:a}", "literal"]
        result = interpolate_deep(data, {"a": "X"}, {})
        assert result == ["X", "literal"]

    def test_passthrough(self):
        data = {"num": 42, "flag": True, "nothing": None}
        assert interpolate_deep(data, {}, {}) == data

    def test_index_in_deep(self):
        data = {"path": "img_{i}.jpg"}
        result = interpolate_deep(data, {}, {}, index=3)
        assert result == {"path": "img_3.jpg"}


# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------

class TestConditionEquals:

    def test_eq_true(self):
        assert evaluate_condition("{keyword:region} == 강남", {"region": "강남"}) is True

    def test_eq_false(self):
        assert evaluate_condition("{keyword:region} == 서초", {"region": "강남"}) is False

    def test_neq_true(self):
        assert evaluate_condition("{keyword:region} != 서초", {"region": "강남"}) is True

    def test_neq_false(self):
        assert evaluate_condition("{keyword:region} != 강남", {"region": "강남"}) is False


class TestConditionIn:

    def test_in_true(self):
        assert evaluate_condition(
            "{keyword:region} in [강남, 서초, 잠실]", {"region": "서초"}
        ) is True

    def test_in_false(self):
        assert evaluate_condition(
            "{keyword:region} in [강남, 서초]", {"region": "잠실"}
        ) is False

    def test_not_in_true(self):
        assert evaluate_condition(
            "{keyword:region} not in [강남, 서초]", {"region": "잠실"}
        ) is True

    def test_not_in_false(self):
        assert evaluate_condition(
            "{keyword:region} not in [강남, 서초]", {"region": "강남"}
        ) is False


class TestConditionEdgeCases:

    def test_empty_is_true(self):
        assert evaluate_condition("", {}) is True

    def test_none_is_true(self):
        assert evaluate_condition(None, {}) is True

    def test_missing_slug_raises(self):
        with pytest.raises(KeyError, match="missing"):
            evaluate_condition("{keyword:missing} == x", {})

    def test_unparseable_raises(self):
        with pytest.raises(ValueError, match="Unparseable"):
            evaluate_condition("gibberish", {"r": "v"})


# ---------------------------------------------------------------------------
# {map:slug} token
# ---------------------------------------------------------------------------

class TestMapToken:

    def test_map_token_resolves(self):
        result = interpolate(
            "{map:photo}", {}, {}, maps={"photo": "gangnam.jpg"},
        )
        assert result == "gangnam.jpg"

    def test_map_token_in_src(self):
        result = interpolate(
            "images/{map:photo}", {}, {}, maps={"photo": "gangnam.jpg"},
        )
        assert result == "images/gangnam.jpg"

    def test_map_mixed_with_keyword(self):
        result = interpolate(
            "{keyword:region} {map:photo}",
            {"region": "강남"}, {},
            maps={"photo": "gangnam.jpg"},
        )
        assert result == "강남 gangnam.jpg"

    def test_map_missing_slug_keeps_token(self):
        result = interpolate("{map:missing}", {}, {}, maps={})
        assert result == "{map:missing}"

    def test_map_none_maps(self):
        result = interpolate("{map:photo}", {}, {}, maps=None)
        assert result == "{map:photo}"

    def test_interpolate_deep_with_maps(self):
        obj = {"src": "{map:photo}", "alt": "{keyword:region}"}
        result = interpolate_deep(
            obj, {"region": "강남"}, {},
            maps={"photo": "gangnam.jpg"},
        )
        assert result == {"src": "gangnam.jpg", "alt": "강남"}
