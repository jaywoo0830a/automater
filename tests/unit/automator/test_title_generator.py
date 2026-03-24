"""
tests/unit/automator/test_title_generator.py
----------------------------------------------
generate_title() and validate_template() unit tests.

DSL format:
    {keyword:slug}  — resolved from TitleOption.values
    {pool:slug}     — random choice from TitleOption.pools
    plain text      — literal (spacing is implicit in the template)

Examples:
    "{pool:salt_prefix} {keyword:region} {keyword:subject} 과외 {pool:salt_suffix}"
    "{pool:salt_prefix} {keyword:region}{keyword:subject}과외 {pool:salt_suffix}"
"""

import random
import pytest

from automator.title_generator import validate_template, generate_title
from automator.options import TitleOption


POOLS = {
    "salt_prefix": ("검증된", "전문"),
    "salt_suffix": ("강력 추천", "즉시 가능"),
}


@pytest.fixture
def option() -> TitleOption:
    return TitleOption(
        template="{keyword:region} {keyword:subject} {keyword:learning_type} {pool:salt_suffix}",
        values={"region": "강남", "subject": "수학", "learning_type": "과외"},
        pools={"salt_suffix": ("강력 추천", "즉시 가능")},
    )


# ---------------------------------------------------------------------------
# validate_template — syntax
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tmpl", [
    "{keyword:region} {keyword:subject}",
    "{pool:salt_prefix} {keyword:region} {keyword:subject}",
    "{keyword:region}{keyword:subject}과외",
    "{pool:salt_prefix} {keyword:region} 과외 {pool:salt_suffix}",
    "{keyword:region} {keyword:school} {keyword:grade} {keyword:subject}",
    "{keyword:region} {keyword:subject} {pool:cta}",
])
def test_validate_template_valid(tmpl):
    validate_template(tmpl)


@pytest.mark.parametrize("tmpl,match", [
    ("",                                              "empty"),
    ("   ",                                           "empty"),
    ("no braces at all",                              "no.*token"),
    ("{keyword:region} {keyword:region}",             "duplicate"),
    ("{pool:salt} {pool:salt}",                       "duplicate"),
    ("{}",                                            "invalid token"),
    ("{keyword:}",                                    "invalid token"),
    ("{:region}",                                     "invalid token"),
    ("{bogus:region}",                                "invalid.*type"),
    ("{region}",                                      "invalid token"),
])
def test_validate_template_invalid(tmpl, match):
    with pytest.raises(ValueError, match=match):
        validate_template(tmpl)


def test_invalid_template_raises_on_generation():
    with pytest.raises(ValueError):
        generate_title(TitleOption(
            template="",
            pools={"salt_suffix": ("강력 추천",)},
        ))


# ---------------------------------------------------------------------------
# fixed_title
# ---------------------------------------------------------------------------

def test_fixed_title_bypasses_template():
    assert generate_title(TitleOption(fixed_title="강남 수학 과외")) == "강남 수학 과외"


def test_fixed_title_is_deterministic():
    opt = TitleOption(fixed_title="강남 수학 과외")
    assert generate_title(opt) == generate_title(opt)


# ---------------------------------------------------------------------------
# keyword substitution
# ---------------------------------------------------------------------------

def test_generate_substitutes_keyword_values(option):
    title = generate_title(option)
    assert "강남" in title
    assert "수학" in title
    assert "과외" in title


def test_generate_includes_pool_value(option):
    title = generate_title(option)
    suffix_set = set(POOLS["salt_suffix"])
    assert any(s in title for s in suffix_set), f"pool value missing: {title!r}"


def test_generate_raises_on_missing_keyword_value():
    with pytest.raises(KeyError):
        generate_title(TitleOption(
            template="{keyword:region} {keyword:missing_slug}",
            values={"region": "강남"},
        ))


def test_generate_raises_on_missing_pool():
    with pytest.raises(KeyError):
        generate_title(TitleOption(
            template="{keyword:region} {pool:missing_pool}",
            values={"region": "강남"},
        ))


# ---------------------------------------------------------------------------
# Literal text preserved
# ---------------------------------------------------------------------------

def test_literal_text_preserved():
    title = generate_title(TitleOption(
        template="{keyword:region} 과외 추천",
        values={"region": "강남"},
    ))
    assert title == "강남 과외 추천"


def test_literal_glued_to_tokens():
    """No space between token and literal when written that way."""
    title = generate_title(TitleOption(
        template="{keyword:region}{keyword:subject}과외",
        values={"region": "강남", "subject": "수학"},
    ))
    assert title == "강남수학과외"


def test_mixed_spacing():
    """Some tokens spaced, some glued, some literals."""
    title = generate_title(TitleOption(
        template="{keyword:region} {keyword:subject}과외 추천",
        values={"region": "강남", "subject": "수학"},
    ))
    assert title == "강남 수학과외 추천"


# ---------------------------------------------------------------------------
# Pool token resolution
# ---------------------------------------------------------------------------

def test_generate_produces_varied_titles(option):
    titles = {generate_title(option) for _ in range(20)}
    assert len(titles) > 1


def test_fixed_seed_produces_same_title(option):
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    assert generate_title(option, rng=rng1) == generate_title(option, rng=rng2)


def test_empty_pool_produces_empty_string():
    title = generate_title(TitleOption(
        template="{keyword:region} {pool:salt_suffix}",
        values={"region": "강남"},
        pools={"salt_suffix": ()},
    ))
    assert title == "강남 "


def test_suffix_pool_resolved():
    suffix_set = set(POOLS["salt_suffix"])
    for _ in range(30):
        title = generate_title(TitleOption(
            template="{keyword:region} {keyword:subject} {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학"},
            pools={"salt_suffix": POOLS["salt_suffix"]},
        ))
        assert any(title.endswith(s) for s in suffix_set)


def test_prefix_pool_resolved():
    prefix_set = set(POOLS["salt_prefix"])
    for _ in range(30):
        title = generate_title(TitleOption(
            template="{pool:salt_prefix} {keyword:region} {keyword:subject}",
            values={"region": "강남", "subject": "수학"},
            pools={"salt_prefix": POOLS["salt_prefix"]},
        ))
        assert any(title.startswith(s) for s in prefix_set)


def test_multiple_pools_in_same_template():
    seen_prefix = set()
    seen_suffix = set()
    for _ in range(50):
        title = generate_title(TitleOption(
            template="{pool:salt_prefix} {keyword:region} {keyword:subject} {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학"},
            pools=POOLS,
        ))
        for s in POOLS["salt_prefix"]:
            if title.startswith(s):
                seen_prefix.add(s)
        for s in POOLS["salt_suffix"]:
            if title.endswith(s):
                seen_suffix.add(s)
    assert len(seen_prefix) > 0
    assert len(seen_suffix) > 0


def test_custom_pool_slug():
    title = generate_title(TitleOption(
        template="{keyword:region} {keyword:subject} {pool:cta}",
        values={"region": "강남", "subject": "수학"},
        pools={"cta": ("지금 신청", "무료 상담")},
    ))
    assert any(s in title for s in ("지금 신청", "무료 상담"))


# ---------------------------------------------------------------------------
# Extra pools/values ignored — no namespace collision needed
# ---------------------------------------------------------------------------

def test_extra_pool_not_in_template_ignored():
    """Pool exists but template doesn't reference it — no error."""
    title = generate_title(TitleOption(
        template="{keyword:region} {keyword:subject}",
        values={"region": "강남", "subject": "수학"},
        pools={"salt_suffix": ("강력 추천",)},
    ))
    assert title == "강남 수학"


def test_extra_value_not_in_template_ignored():
    """Value exists but template doesn't reference it — no error."""
    title = generate_title(TitleOption(
        template="{keyword:region}",
        values={"region": "강남", "subject": "수학"},
    ))
    assert title == "강남"


def test_same_slug_different_type_no_collision():
    """keyword:region and pool:region are distinct — no collision."""
    title = generate_title(TitleOption(
        template="{keyword:region} {pool:region}",
        values={"region": "강남"},
        pools={"region": ("서초", "용산")},
    ))
    assert "강남" in title
    assert any(s in title for s in ("서초", "용산"))


# ---------------------------------------------------------------------------
# Multi-dimension templates
# ---------------------------------------------------------------------------

def test_three_dimension_template():
    title = generate_title(TitleOption(
        template="{keyword:region} {keyword:target_audience} {keyword:subject} {pool:salt_suffix}",
        values={"region": "원주", "target_audience": "성인", "subject": "영어회화"},
        pools={"salt_suffix": POOLS["salt_suffix"]},
    ))
    assert "원주" in title
    assert "성인" in title
    assert "영어회화" in title


def test_five_dimension_template():
    title = generate_title(TitleOption(
        template="{keyword:region} {keyword:school} {keyword:grade} {keyword:subject} {keyword:learning_type} {pool:salt_suffix}",
        values={
            "region": "원주", "school": "OO중", "grade": "중1",
            "subject": "수학", "learning_type": "과외",
        },
        pools={"salt_suffix": POOLS["salt_suffix"]},
    ))
    assert all(v in title for v in ["원주", "OO중", "중1", "수학", "과외"])

