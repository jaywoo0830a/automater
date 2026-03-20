"""
tests/test_title_generator.py
----------------------------
generate_title() and validate_template() unit tests.
"""

import random
import pytest

from automator.title_generator import validate_template, generate_title
from automator.options import TitleOption


PREFIX_SALTS = ("검증된", "전문")
SUFFIX_SALTS = ("강력 추천", "즉시 가능")
ALL_SALTS    = set(PREFIX_SALTS) | set(SUFFIX_SALTS)


@pytest.fixture
def option() -> TitleOption:
    return TitleOption(
        template      = "{region} {subject} {learning_type} {salt}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    )


# ---------------------------------------------------------------------------
# validate_template
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("tmpl", [
    "{region} {subject} {learning_type} {salt}",
    "{salt} {region} {subject} {learning_type}",
    "{region} {salt} {subject} {learning_type}",
    "{region} {target_audience} {subject} {salt}",
    "{region} {school} {grade} {subject} {learning_type} {salt}",
    "{region} {subject}",
])
def test_validate_template_valid(tmpl):
    validate_template(tmpl)


@pytest.mark.unit
@pytest.mark.parametrize("tmpl,match", [
    ("",                                     "empty"),
    ("   ",                                  "empty"),
    ("{region} {region} {salt}",             "duplicate"),
    ("no braces at all",                     "no.*token"),
    ("{} {subject}",                         "empty braces"),
    ("{123bad} {subject}",                   "not a valid identifier"),
])
def test_validate_template_invalid(tmpl, match):
    with pytest.raises(ValueError, match=match):
        validate_template(tmpl)


@pytest.mark.unit
def test_invalid_template_raises_on_generation():
    with pytest.raises(ValueError):
        generate_title(TitleOption(template="", prefix_salts=PREFIX_SALTS))


# ---------------------------------------------------------------------------
# fixed_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fixed_title_bypasses_template():
    assert generate_title(TitleOption(fixed_title="강남 수학 과외")) == "강남 수학 과외"


@pytest.mark.unit
def test_fixed_title_is_deterministic():
    opt = TitleOption(fixed_title="강남 수학 과외")
    assert generate_title(opt) == generate_title(opt)


# ---------------------------------------------------------------------------
# values substitution
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_substitutes_values(option):
    title = generate_title(option)
    assert "강남" in title
    assert "수학" in title
    assert "과외" in title


@pytest.mark.unit
def test_generate_includes_salt(option):
    title = generate_title(option)
    assert any(s in title for s in ALL_SALTS), f"솔트 없음: {title!r}"


@pytest.mark.unit
def test_generate_without_salt_token():
    title = generate_title(TitleOption(
        template      = "{region} {subject} {learning_type}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    assert title == "강남 수학 과외"


@pytest.mark.unit
def test_generate_raises_on_missing_value():
    with pytest.raises(KeyError):
        generate_title(TitleOption(
            template      = "{region} {subject} {missing_slug}",
            values        = {"region": "강남", "subject": "수학"},
            prefix_salts  = PREFIX_SALTS,
            suffix_salts  = SUFFIX_SALTS,
        ))


@pytest.mark.unit
def test_generate_produces_varied_titles(option):
    titles = {generate_title(option) for _ in range(20)}
    assert len(titles) > 1


@pytest.mark.unit
def test_fixed_seed_produces_same_title(option):
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    assert generate_title(option, rng=rng1) == generate_title(option, rng=rng2)


@pytest.mark.unit
def test_empty_salts_produces_empty_salt_token():
    title = generate_title(TitleOption(
        template = "{region} {salt}",
        values   = {"region": "강남"},
    ))
    assert title == "강남 "


# ---------------------------------------------------------------------------
# Salt pool selection by {salt} position
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_suffix_salt_used_when_salt_is_last():
    suffix_set = set(SUFFIX_SALTS)
    for _ in range(30):
        title = generate_title(TitleOption(
            template     = "{region} {subject} {learning_type} {salt}",
            values       = {"region": "강남", "subject": "수학", "learning_type": "과외"},
            prefix_salts = PREFIX_SALTS,
            suffix_salts = SUFFIX_SALTS,
        ))
        assert any(title.endswith(s) for s in suffix_set)


@pytest.mark.unit
def test_prefix_salt_used_when_salt_is_first():
    prefix_set = set(PREFIX_SALTS)
    for _ in range(30):
        title = generate_title(TitleOption(
            template     = "{salt} {region} {subject} {learning_type}",
            values       = {"region": "강남", "subject": "수학", "learning_type": "과외"},
            prefix_salts = PREFIX_SALTS,
            suffix_salts = SUFFIX_SALTS,
        ))
        assert any(title.startswith(s) for s in prefix_set)


@pytest.mark.unit
def test_all_salts_used_when_salt_is_middle():
    seen = set()
    for _ in range(50):
        title = generate_title(TitleOption(
            template     = "{region} {salt} {subject} {learning_type}",
            values       = {"region": "강남", "subject": "수학", "learning_type": "과외"},
            prefix_salts = PREFIX_SALTS,
            suffix_salts = SUFFIX_SALTS,
        ))
        for s in ALL_SALTS:
            if s in title:
                seen.add(s)
    assert len(seen) > 1


# ---------------------------------------------------------------------------
# Multi-dimension templates
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_three_dimension_template():
    title = generate_title(TitleOption(
        template     = "{region} {target_audience} {subject} {salt}",
        values       = {"region": "원주", "target_audience": "성인", "subject": "영어회화"},
        suffix_salts = SUFFIX_SALTS,
    ))
    assert "원주" in title
    assert "성인" in title
    assert "영어회화" in title


@pytest.mark.unit
def test_five_dimension_template():
    title = generate_title(TitleOption(
        template = "{region} {school} {grade} {subject} {learning_type} {salt}",
        values   = {
            "region": "원주", "school": "OO중", "grade": "중1",
            "subject": "수학", "learning_type": "과외",
        },
        suffix_salts = SUFFIX_SALTS,
    ))
    assert all(v in title for v in ["원주", "OO중", "중1", "수학", "과외"])
