"""
tests/unit/cli/test_dsl.py
----------------------------
DSL token interpolation for arbitrary strings.

Same tokens as title_generator:
    {keyword:slug}  → values[slug]
    {keywords}      → all values joined
    {pool:slug}     → random from pools[slug]
"""

import random
import pytest

from cli.dsl import interpolate


# ---------------------------------------------------------------------------
# {keyword:slug}
# ---------------------------------------------------------------------------

class TestKeywordToken:

    def test_single_keyword(self):
        result = interpolate("{keyword:region} 소개", {"region": "강남"}, {})
        assert result == "강남 소개"

    def test_multiple_keywords(self):
        result = interpolate(
            "{keyword:region} {keyword:subject}",
            {"region": "강남", "subject": "수학"}, {},
        )
        assert result == "강남 수학"

    def test_glued_keywords(self):
        result = interpolate(
            "{keyword:region}{keyword:subject}과외",
            {"region": "강남", "subject": "수학"}, {},
        )
        assert result == "강남수학과외"

    def test_missing_keyword_raises(self):
        with pytest.raises(KeyError, match="missing"):
            interpolate("{keyword:missing}", {}, {})


# ---------------------------------------------------------------------------
# {keywords}
# ---------------------------------------------------------------------------

class TestKeywordsToken:

    def test_joins_all_values(self):
        result = interpolate("{keywords} 과외", {"region": "강남", "subject": "수학"}, {})
        assert result == "강남 수학 과외"

    def test_preserves_order(self):
        result = interpolate("{keywords}", {"z": "C", "a": "A", "m": "B"}, {})
        assert result == "C A B"

    def test_single_value(self):
        result = interpolate("{keywords}", {"region": "강남"}, {})
        assert result == "강남"


# ---------------------------------------------------------------------------
# {pool:slug}
# ---------------------------------------------------------------------------

class TestPoolToken:

    def test_pool_selects_from_list(self):
        pools = {"prefix": ["검증된", "전문"]}
        result = interpolate("{pool:prefix}", {}, pools, rng=random.Random(42))
        assert result in ("검증된", "전문")

    def test_missing_pool_raises(self):
        with pytest.raises(KeyError, match="missing"):
            interpolate("{pool:missing}", {}, {})

    def test_empty_pool_returns_empty(self):
        result = interpolate("{pool:empty}", {}, {"empty": []})
        assert result == ""

    def test_deterministic_with_seed(self):
        pools = {"p": ["A", "B", "C"]}
        r1 = interpolate("{pool:p}", {}, pools, rng=random.Random(42))
        r2 = interpolate("{pool:p}", {}, pools, rng=random.Random(42))
        assert r1 == r2


# ---------------------------------------------------------------------------
# Mixed / Literals
# ---------------------------------------------------------------------------

class TestMixed:

    def test_all_token_types(self):
        result = interpolate(
            "{pool:prefix} {keywords} 과외 {keyword:region} 특집",
            {"region": "강남", "subject": "수학"},
            {"prefix": ["검증된"]},
        )
        assert result == "검증된 강남 수학 과외 강남 특집"

    def test_no_tokens_returns_as_is(self):
        result = interpolate("리터럴 텍스트만", {}, {})
        assert result == "리터럴 텍스트만"

    def test_empty_string(self):
        result = interpolate("", {}, {})
        assert result == ""


# ---------------------------------------------------------------------------
# interpolate_deep — recursive dict/list interpolation
# ---------------------------------------------------------------------------

class TestInterpolateDeep:

    def test_dict_values_interpolated(self):
        from cli.dsl import interpolate_deep
        data = {"text": "{keywords} 소개", "level": 2}
        result = interpolate_deep(data, {"region": "강남"}, {})
        assert result == {"text": "강남 소개", "level": 2}

    def test_nested_dict(self):
        from cli.dsl import interpolate_deep
        data = {"outer": {"inner": "{keyword:region}"}}
        result = interpolate_deep(data, {"region": "강남"}, {})
        assert result == {"outer": {"inner": "강남"}}

    def test_list_items_interpolated(self):
        from cli.dsl import interpolate_deep
        data = ["{keyword:a}", "literal", "{keywords}"]
        result = interpolate_deep(data, {"a": "X", "b": "Y"}, {})
        assert result == ["X", "literal", "X Y"]

    def test_non_string_passthrough(self):
        from cli.dsl import interpolate_deep
        data = {"num": 42, "flag": True, "nothing": None}
        result = interpolate_deep(data, {}, {})
        assert result == {"num": 42, "flag": True, "nothing": None}
