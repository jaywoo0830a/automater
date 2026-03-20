"""
tests/test_options_title.py
----------------------------
TitleGenerator 와 TitleOption 단위 테스트.

- 솔트 데이터는 TitleOption.prefix_salts / suffix_salts 튜플로 직접 전달.
- template 형식: "{slug}" 토큰, {salt} 는 특수 처리.
- values dict 로 토큰 치환.
"""

import pytest

from automator.title_generator import (
    validate_template,
    TitleGenerator,
)
from automator.options import TitleOption


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREFIX_SALTS = ("검증된", "전문")
SUFFIX_SALTS = ("강력 추천", "즉시 가능")
ALL_SALTS    = set(PREFIX_SALTS) | set(SUFFIX_SALTS)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    "{region} {subject}",                    # salt 없어도 유효
])
def test_validate_template_valid(tmpl):
    validate_template(tmpl)   # must not raise


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
def test_invalid_template_raises_on_construction():
    with pytest.raises(ValueError):
        TitleGenerator(TitleOption(
            template      = "",
            prefix_salts  = PREFIX_SALTS,
        ))


# ---------------------------------------------------------------------------
# TitleGenerator — fixed_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fixed_title_bypasses_template():
    gen = TitleGenerator(TitleOption(fixed_title="강남 수학 과외"))
    assert gen.generate() == "강남 수학 과외"


@pytest.mark.unit
def test_fixed_title_is_deterministic():
    gen = TitleGenerator(TitleOption(fixed_title="강남 수학 과외"))
    assert gen.generate() == gen.generate()


# ---------------------------------------------------------------------------
# TitleGenerator — values substitution
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_substitutes_values(option):
    gen   = TitleGenerator(option)
    title = gen.generate()
    assert "강남" in title
    assert "수학" in title
    assert "과외" in title


@pytest.mark.unit
def test_generate_includes_salt(option):
    gen   = TitleGenerator(option)
    title = gen.generate()
    assert any(s in title for s in ALL_SALTS), f"솔트 없음: {title!r}"


@pytest.mark.unit
def test_generate_without_salt_token():
    """template 에 {salt} 없으면 솔트 삽입 없이 values 만 치환."""
    gen = TitleGenerator(TitleOption(
        template      = "{region} {subject} {learning_type}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    title = gen.generate()
    assert title == "강남 수학 과외"


@pytest.mark.unit
def test_generate_raises_on_missing_value():
    """values 에 없는 {slug} 토큰이 있으면 KeyError."""
    gen = TitleGenerator(TitleOption(
        template      = "{region} {subject} {missing_slug}",
        values        = {"region": "강남", "subject": "수학"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    with pytest.raises(KeyError):
        gen.generate()


@pytest.mark.unit
def test_generate_produces_varied_titles(option):
    """솔트가 랜덤이므로 여러 번 호출하면 다른 제목이 나온다."""
    gen    = TitleGenerator(option)
    titles = {gen.generate() for _ in range(20)}
    assert len(titles) > 1


@pytest.mark.unit
def test_fixed_seed_produces_same_title(option):
    import random
    rng   = random.Random(42)
    gen   = TitleGenerator(option, rng=rng)
    title = gen.generate()
    rng2  = random.Random(42)
    gen2  = TitleGenerator(option, rng=rng2)
    assert gen2.generate() == title


@pytest.mark.unit
def test_empty_salts_produces_empty_salt_token():
    """솔트가 비어있으면 {salt} 위치에 빈 문자열이 들어간다."""
    gen = TitleGenerator(TitleOption(
        template = "{region} {salt}",
        values   = {"region": "강남"},
    ))
    assert gen.generate() == "강남 "


# ---------------------------------------------------------------------------
# Salt pool selection by {salt} position
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_suffix_salt_used_when_salt_is_last():
    """template 마지막 → suffix_salts 에서 선택."""
    gen = TitleGenerator(TitleOption(
        template      = "{region} {subject} {learning_type} {salt}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    suffix_set = set(SUFFIX_SALTS)
    prefix_set = set(PREFIX_SALTS)
    for _ in range(30):
        title = gen.generate()
        assert any(title.endswith(s) for s in suffix_set), f"suffix_salt가 끝에 와야 함: {title!r}"
        assert not any(title.endswith(s) for s in prefix_set), f"prefix_salt가 끝에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_prefix_salt_used_when_salt_is_first():
    """template 첫 번째 → prefix_salts 에서 선택."""
    gen = TitleGenerator(TitleOption(
        template      = "{salt} {region} {subject} {learning_type}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    prefix_set = set(PREFIX_SALTS)
    suffix_set = set(SUFFIX_SALTS)
    for _ in range(30):
        title = gen.generate()
        assert any(title.startswith(s) for s in prefix_set), f"prefix_salt가 앞에 와야 함: {title!r}"
        assert not any(title.startswith(s) for s in suffix_set), f"suffix_salt가 앞에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_all_salts_used_when_salt_is_middle():
    gen = TitleGenerator(TitleOption(
        template      = "{region} {salt} {subject} {learning_type}",
        values        = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        prefix_salts  = PREFIX_SALTS,
        suffix_salts  = SUFFIX_SALTS,
    ))
    seen = set()
    for _ in range(50):
        title = gen.generate()
        for s in ALL_SALTS:
            if s in title:
                seen.add(s)
    assert len(seen) > 1, f"중간 위치에서 다양한 솔트가 선택되어야 함: {seen}"


# ---------------------------------------------------------------------------
# Multi-dimension templates
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_three_dimension_template():
    """{region} {target_audience} {subject} — 학원/과외와 다른 구조."""
    gen = TitleGenerator(TitleOption(
        template      = "{region} {target_audience} {subject} {salt}",
        values        = {"region": "원주", "target_audience": "성인", "subject": "영어회화"},
        suffix_salts  = SUFFIX_SALTS,
    ))
    title = gen.generate()
    assert "원주" in title
    assert "성인" in title
    assert "영어회화" in title


@pytest.mark.unit
def test_five_dimension_template():
    """{region} {school} {grade} {subject} {learning_type} — 5차원 케이스."""
    gen = TitleGenerator(TitleOption(
        template = "{region} {school} {grade} {subject} {learning_type} {salt}",
        values   = {
            "region": "원주",
            "school": "OO중",
            "grade":  "중1",
            "subject": "수학",
            "learning_type": "과외",
        },
        suffix_salts = SUFFIX_SALTS,
    ))
    title = gen.generate()
    assert all(v in title for v in ["원주", "OO중", "중1", "수학", "과외"])
