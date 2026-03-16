"""
tests/test_title_unit.py
--------------------------
TitleGenerator 와 TitleOption 단위 테스트.

- salts.json 만 사용 (regions.json / subjects.json 제거)
- template 형식: "{slug}" 토큰, {salt} 는 특수 처리
- values dict 로 토큰 치환
"""

import json
import pytest
from pathlib import Path

from automator.title_generator import (
    load_salts,
    validate_template,
    TitleGenerator,
)
from automator.options import TitleOption


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def salts_file(tmp_path: Path) -> Path:
    data = {
        "prefix_salts": ["검증된", "전문"],
        "suffix_salts": ["강력 추천", "즉시 가능"],
    }
    p = tmp_path / "salts.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def option(salts_file) -> TitleOption:
    return TitleOption(
        template    = "{region} {subject} {learning_type} {salt}",
        values      = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        salt_preset = str(salts_file),
    )


# ---------------------------------------------------------------------------
# load_salts
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_load_salts_returns_prefix_and_suffix(salts_file):
    result = load_salts(salts_file)
    assert "prefix" in result and "suffix" in result


@pytest.mark.unit
def test_load_salts_all_returns_combined(salts_file):
    result = load_salts(salts_file)
    assert set(result["all"]) == set(result["prefix"]) | set(result["suffix"])


@pytest.mark.unit
def test_load_salts_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_salts(Path("/no/such/salts.json"))


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
    validate_template(tmpl)   # 예외 없이 통과


@pytest.mark.unit
@pytest.mark.parametrize("tmpl,reason", [
    ("",                                     "empty"),
    ("   ",                                  "whitespace only"),
    ("{region} {region} {salt}",             "duplicate"),
    ("no braces at all",                     "no tokens"),
    ("{} {subject}",                         "empty brace"),
    ("{123bad} {subject}",                   "invalid identifier"),
])
def test_validate_template_invalid(tmpl, reason):
    with pytest.raises(ValueError, match=reason if reason not in ("empty", "whitespace only", "no tokens", "duplicate", "empty brace", "invalid identifier") else ""):
        validate_template(tmpl)


@pytest.mark.unit
def test_invalid_template_raises_on_construction(salts_file):
    with pytest.raises(ValueError):
        TitleGenerator(TitleOption(
            template    = "",
            salt_preset = str(salts_file),
        ))


# ---------------------------------------------------------------------------
# TitleGenerator — fixed_title
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fixed_title_bypasses_template(salts_file):
    gen = TitleGenerator(TitleOption(fixed_title="강남 수학 과외"))
    assert gen.generate() == "강남 수학 과외"


@pytest.mark.unit
def test_fixed_title_is_deterministic(salts_file):
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
    suffix_salts = {"강력 추천", "즉시 가능"}
    prefix_salts = {"검증된", "전문"}
    all_salts = suffix_salts | prefix_salts
    assert any(s in title for s in all_salts), f"솔트 없음: {title!r}"


@pytest.mark.unit
def test_generate_without_salt_token(salts_file):
    """template 에 {salt} 없으면 솔트 삽입 없이 values 만 치환."""
    gen = TitleGenerator(TitleOption(
        template    = "{region} {subject} {learning_type}",
        values      = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        salt_preset = str(salts_file),
    ))
    title = gen.generate()
    assert title == "강남 수학 과외"


@pytest.mark.unit
def test_generate_raises_on_missing_value(salts_file):
    """values 에 없는 {slug} 토큰이 있으면 KeyError."""
    gen = TitleGenerator(TitleOption(
        template    = "{region} {subject} {missing_slug}",
        values      = {"region": "강남", "subject": "수학"},
        salt_preset = str(salts_file),
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


# ---------------------------------------------------------------------------
# Salt pool selection by {salt} position
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_suffix_salt_used_when_salt_is_last(salts_file):
    """template 마지막 → suffix_salts 에서 선택."""
    gen = TitleGenerator(TitleOption(
        template    = "{region} {subject} {learning_type} {salt}",
        values      = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        salt_preset = str(salts_file),
    ))
    suffix_salts = {"강력 추천", "즉시 가능"}
    prefix_salts = {"검증된", "전문"}
    for _ in range(30):
        title = gen.generate()
        assert any(title.endswith(s) for s in suffix_salts), f"suffix_salt가 끝에 와야 함: {title!r}"
        assert not any(title.endswith(s) for s in prefix_salts), f"prefix_salt가 끝에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_prefix_salt_used_when_salt_is_first(salts_file):
    """template 첫 번째 → prefix_salts 에서 선택."""
    gen = TitleGenerator(TitleOption(
        template    = "{salt} {region} {subject} {learning_type}",
        values      = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        salt_preset = str(salts_file),
    ))
    prefix_salts = {"검증된", "전문"}
    suffix_salts = {"강력 추천", "즉시 가능"}
    for _ in range(30):
        title = gen.generate()
        assert any(title.startswith(s) for s in prefix_salts), f"prefix_salt가 앞에 와야 함: {title!r}"
        assert not any(title.startswith(s) for s in suffix_salts), f"suffix_salt가 앞에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_all_salts_used_when_salt_is_middle(salts_file):
    gen = TitleGenerator(TitleOption(
        template    = "{region} {salt} {subject} {learning_type}",
        values      = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        salt_preset = str(salts_file),
    ))
    all_salts = {"검증된", "전문", "강력 추천", "즉시 가능"}
    seen = set()
    for _ in range(50):
        title = gen.generate()
        for s in all_salts:
            if s in title:
                seen.add(s)
    assert len(seen) > 1, f"중간 위치에서 다양한 솔트가 선택되어야 함: {seen}"


# ---------------------------------------------------------------------------
# Multi-dimension templates (원주 성인 영어회화 케이스)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_three_dimension_template(salts_file):
    """{region} {target_audience} {subject} — 학원/과외와 다른 구조."""
    gen = TitleGenerator(TitleOption(
        template    = "{region} {target_audience} {subject} {salt}",
        values      = {"region": "원주", "target_audience": "성인", "subject": "영어회화"},
        salt_preset = str(salts_file),
    ))
    title = gen.generate()
    assert "원주" in title
    assert "성인" in title
    assert "영어회화" in title


@pytest.mark.unit
def test_five_dimension_template(salts_file):
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
        salt_preset = str(salts_file),
    ))
    title = gen.generate()
    assert all(v in title for v in ["원주", "OO중", "중1", "수학", "과외"])
