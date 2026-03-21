"""
tests/test_title_generator.py
----------------------------
generate_title() and validate_template() unit tests.

Pools-based design: CampaignPalette slugs map directly to template tokens.
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
        template = "{region} {subject} {learning_type} {salt_suffix}",
        values   = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        pools    = {"salt_suffix": ("강력 추천", "즉시 가능")},
    )


# ---------------------------------------------------------------------------
# validate_template
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tmpl", [
    "{region} {subject} {learning_type} {salt_suffix}",
    "{salt_prefix} {region} {subject} {learning_type}",
    "{region} {cta} {subject} {learning_type}",
    "{region} {target_audience} {subject} {salt_suffix}",
    "{region} {school} {grade} {subject} {learning_type} {salt_suffix}",
    "{region} {subject}",
])
def test_validate_template_valid(tmpl):
    validate_template(tmpl)


@pytest.mark.parametrize("tmpl,match", [
    ("",                                     "empty"),
    ("   ",                                  "empty"),
    ("{region} {region} {salt_suffix}",      "duplicate"),
    ("no braces at all",                     "no.*token"),
    ("{} {subject}",                         "empty braces"),
    ("{123bad} {subject}",                   "not a valid identifier"),
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
# values substitution
# ---------------------------------------------------------------------------

def test_generate_substitutes_values(option):
    title = generate_title(option)
    assert "강남" in title
    assert "수학" in title
    assert "과외" in title


def test_generate_includes_pool_value(option):
    title = generate_title(option)
    suffix_set = set(POOLS["salt_suffix"])
    assert any(s in title for s in suffix_set), f"pool value missing: {title!r}"


def test_generate_without_pool_token():
    """Pool exists but template doesn't reference it — no error, pool ignored."""
    title = generate_title(TitleOption(
        template = "{region} {subject} {learning_type}",
        values   = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        pools    = {"salt_suffix": ("강력 추천",)},
    ))
    assert title == "강남 수학 과외"


def test_generate_raises_on_missing_value():
    with pytest.raises(KeyError):
        generate_title(TitleOption(
            template = "{region} {subject} {missing_slug}",
            values   = {"region": "강남", "subject": "수학"},
        ))


def test_generate_produces_varied_titles(option):
    titles = {generate_title(option) for _ in range(20)}
    assert len(titles) > 1


def test_fixed_seed_produces_same_title(option):
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    assert generate_title(option, rng=rng1) == generate_title(option, rng=rng2)


def test_empty_pool_produces_empty_token():
    title = generate_title(TitleOption(
        template = "{region} {salt_suffix}",
        values   = {"region": "강남"},
        pools    = {"salt_suffix": ()},
    ))
    assert title == "강남 "


# ---------------------------------------------------------------------------
# Pool token resolution — palette slug = template token
# ---------------------------------------------------------------------------

def test_suffix_pool_resolved_in_template():
    suffix_set = set(POOLS["salt_suffix"])
    for _ in range(30):
        title = generate_title(TitleOption(
            template = "{region} {subject} {salt_suffix}",
            values   = {"region": "강남", "subject": "수학"},
            pools    = {"salt_suffix": POOLS["salt_suffix"]},
        ))
        assert any(title.endswith(s) for s in suffix_set)


def test_prefix_pool_resolved_in_template():
    prefix_set = set(POOLS["salt_prefix"])
    for _ in range(30):
        title = generate_title(TitleOption(
            template = "{salt_prefix} {region} {subject}",
            values   = {"region": "강남", "subject": "수학"},
            pools    = {"salt_prefix": POOLS["salt_prefix"]},
        ))
        assert any(title.startswith(s) for s in prefix_set)


def test_multiple_pools_in_same_template():
    seen_prefix = set()
    seen_suffix = set()
    for _ in range(50):
        title = generate_title(TitleOption(
            template = "{salt_prefix} {region} {subject} {salt_suffix}",
            values   = {"region": "강남", "subject": "수학"},
            pools    = POOLS,
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
    """Any palette slug works as a template token — not just salt_*."""
    title = generate_title(TitleOption(
        template = "{region} {subject} {cta}",
        values   = {"region": "강남", "subject": "수학"},
        pools    = {"cta": ("지금 신청", "무료 상담")},
    ))
    assert any(s in title for s in ("지금 신청", "무료 상담"))


# ---------------------------------------------------------------------------
# Namespace collision detection
# ---------------------------------------------------------------------------

def test_collision_raises_value_error():
    """Same slug in both values and pools → ValueError."""
    with pytest.raises(ValueError, match="collision"):
        generate_title(TitleOption(
            template = "{region} {subject}",
            values   = {"region": "강남", "subject": "수학"},
            pools    = {"region": ("서초", "용산")},
        ))


def test_no_collision_when_disjoint():
    title = generate_title(TitleOption(
        template = "{region} {salt_suffix}",
        values   = {"region": "강남"},
        pools    = {"salt_suffix": ("추천",)},
    ))
    assert "강남" in title
    assert "추천" in title


# ---------------------------------------------------------------------------
# Multi-dimension templates
# ---------------------------------------------------------------------------

def test_three_dimension_template():
    title = generate_title(TitleOption(
        template = "{region} {target_audience} {subject} {salt_suffix}",
        values   = {"region": "원주", "target_audience": "성인", "subject": "영어회화"},
        pools    = {"salt_suffix": POOLS["salt_suffix"]},
    ))
    assert "원주" in title
    assert "성인" in title
    assert "영어회화" in title


def test_five_dimension_template():
    title = generate_title(TitleOption(
        template = "{region} {school} {grade} {subject} {learning_type} {salt_suffix}",
        values   = {
            "region": "원주", "school": "OO중", "grade": "중1",
            "subject": "수학", "learning_type": "과외",
        },
        pools    = {"salt_suffix": POOLS["salt_suffix"]},
    ))
    assert all(v in title for v in ["원주", "OO중", "중1", "수학", "과외"])
