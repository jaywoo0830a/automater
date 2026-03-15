"""
tests/test_title_unit.py
------------------------
Unit tests for TitleGenerator and preset loaders.

모든 테스트는 tmp_path에 인라인 픽스처 JSON을 생성해서 사용한다.
실제 presets/title/*.json 파일 없이도 통과한다.
"""

import json
import random
import pytest
from pathlib import Path

from automator.options import TitleOption, TITLE_TOKENS
from automator.title_generator import (
    TitleGenerator,
    validate_template,
    load_regions,
    load_subjects,
    load_salts,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def regions_file(tmp_path: Path) -> Path:
    data = {
        "regions": [
            {"base_name": "대치",  "full_name": "대치동",  "tier": "핵심"},
            {"base_name": "목동",  "full_name": "목동",    "tier": "핵심"},
            {"base_name": "수원",  "full_name": "수원시",  "tier": "전국"},
        ]
    }
    p = tmp_path / "regions.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def subjects_file(tmp_path: Path) -> Path:
    data = {"subjects": ["영어", "수학", "국어"]}
    p = tmp_path / "subjects.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


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
def option(regions_file, subjects_file, salts_file) -> TitleOption:
    return TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
    )


@pytest.fixture
def gen(option) -> TitleGenerator:
    return TitleGenerator(option, rng=random.Random(42))


# ===========================================================================
# 1. Preset loaders
# ===========================================================================

@pytest.mark.unit
def test_load_regions_returns_list(regions_file):
    assert len(load_regions(regions_file)) == 3


@pytest.mark.unit
def test_load_regions_entry_has_required_keys(regions_file):
    for entry in load_regions(regions_file):
        assert {"base_name", "full_name", "tier"} <= entry.keys()


@pytest.mark.unit
def test_load_subjects_returns_list(subjects_file):
    assert load_subjects(subjects_file) == ["영어", "수학", "국어"]


@pytest.mark.unit
def test_load_salts_returns_prefix_and_suffix(salts_file):
    """load_salts()는 prefix/suffix 두 리스트를 가진 dict를 반환한다."""
    result = load_salts(salts_file)
    assert isinstance(result, dict), "dict 반환 필요"
    assert "prefix" in result and "suffix" in result
    assert "검증된" in result["prefix"]
    assert "강력 추천" in result["suffix"]


@pytest.mark.unit
def test_load_salts_all_returns_combined(salts_file):
    """all 키는 prefix + suffix 합집합이다."""
    result = load_salts(salts_file)
    assert set(result["all"]) == set(result["prefix"]) | set(result["suffix"])


@pytest.mark.unit
def test_load_regions_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_regions(Path("/no/such/regions.json"))


@pytest.mark.unit
def test_load_subjects_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_subjects(Path("/no/such/subjects.json"))


@pytest.mark.unit
def test_load_salts_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_salts(Path("/no/such/salts.json"))


# ===========================================================================
# 2. validate_template
# ===========================================================================

@pytest.mark.unit
@pytest.mark.parametrize("tmpl", [
    "지역+과목+학습형태+솔트",   # 기본 (솔트 맨 끝)
    "솔트+지역+과목+학습형태",   # 솔트 맨 앞
    "지역+솔트+과목+학습형태",   # 솔트 중간
    "과목+지역+학습형태+솔트",   # 과목 먼저
])
def test_validate_template_valid(tmpl):
    validate_template(tmpl)  # should not raise


@pytest.mark.unit
@pytest.mark.parametrize("tmpl, expected_msg", [
    ("지역+과목+솔트",               "missing"),     # 학습형태 누락
    ("지역+과목+학습형태+솔트+솔트", "duplicate"),   # 솔트 중복
    ("지역+과목+학습형태+unknown",   "Unknown"),     # 알 수 없는 토큰
    ("",                             "empty"),       # 빈 문자열
])
def test_validate_template_invalid(tmpl, expected_msg):
    with pytest.raises(ValueError, match=expected_msg):
        validate_template(tmpl)


@pytest.mark.unit
def test_title_tokens_contains_all_four():
    assert TITLE_TOKENS == {"지역", "과목", "학습형태", "솔트"}


# ===========================================================================
# 3. TitleGenerator — 생성 시 템플릿 검사
# ===========================================================================

@pytest.mark.unit
def test_invalid_template_raises_on_construction(regions_file, subjects_file, salts_file):
    """잘못된 템플릿은 TitleGenerator 생성 시 ValueError."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="지역+과목+솔트",  # 학습형태 누락
    )
    with pytest.raises(ValueError, match="missing"):
        TitleGenerator(opt)


# ===========================================================================
# 4. include_suffix — 행정구역 단위 포함 여부
# ===========================================================================

@pytest.mark.unit
def test_include_suffix_true_uses_full_name(regions_file, subjects_file, salts_file):
    """include_suffix=True → '대치동', '수원시' 형태 사용."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        include_suffix=True,
    )
    titles = [TitleGenerator(opt, rng=random.Random(i)).generate() for i in range(30)]
    for title in titles:
        # base_name에만 있는 '대치'(동 없이)나 '수원'(시 없이)이 단독으로 나오면 안 된다
        # '대치동'은 '대치'를 포함하므로, '대치'가 있을 때 '대치동'도 있어야 한다
        if "대치" in title:
            assert "대치동" in title, f"full_name이어야 함: {title!r}"
        if "수원" in title:
            assert "수원시" in title, f"full_name이어야 함: {title!r}"


@pytest.mark.unit
def test_include_suffix_false_uses_base_name(regions_file, subjects_file, salts_file):
    """include_suffix=False → '대치', '수원' 형태 사용. 행정구역 단위 없음."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        include_suffix=False,
    )
    titles = [TitleGenerator(opt, rng=random.Random(i)).generate() for i in range(30)]
    for title in titles:
        assert "대치동" not in title, f"full_name이 포함됨: {title!r}"
        assert "수원시" not in title, f"full_name이 포함됨: {title!r}"


# ===========================================================================
# 5. Template — 솔트 위치
# ===========================================================================

@pytest.mark.unit
def test_suffix_salt_used_when_salt_is_last(regions_file, subjects_file, salts_file):
    """
    솔트가 템플릿 마지막 → suffix_salts에서 선택.
    기본 템플릿: 지역+과목+학습형태+솔트
    """
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="지역+과목+학습형태+솔트",
    )
    suffix_salts = {"강력 추천", "즉시 가능"}
    prefix_salts = {"검증된", "전문"}
    for seed in range(30):
        title = TitleGenerator(opt, rng=random.Random(seed)).generate()
        assert any(title.endswith(s) for s in suffix_salts),             f"suffix_salt가 끝에 와야 함: {title!r}"
        assert not any(title.endswith(s) for s in prefix_salts),             f"prefix_salt가 끝에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_prefix_salt_used_when_salt_is_first(regions_file, subjects_file, salts_file):
    """
    솔트가 템플릿 첫 번째 → prefix_salts에서 선택.
    템플릿: 솔트+지역+과목+학습형태
    """
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="솔트+지역+과목+학습형태",
    )
    prefix_salts = {"검증된", "전문"}
    suffix_salts = {"강력 추천", "즉시 가능"}
    for seed in range(30):
        title = TitleGenerator(opt, rng=random.Random(seed)).generate()
        assert any(title.startswith(s) for s in prefix_salts),             f"prefix_salt가 앞에 와야 함: {title!r}"
        assert not any(title.startswith(s) for s in suffix_salts),             f"suffix_salt가 앞에 오면 안 됨: {title!r}"


@pytest.mark.unit
def test_all_salts_used_when_salt_is_middle(regions_file, subjects_file, salts_file):
    """
    솔트가 템플릿 중간 → prefix + suffix 합집합에서 선택.
    템플릿: 지역+솔트+과목+학습형태
    """
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="지역+솔트+과목+학습형태",
    )
    all_salts = {"검증된", "전문", "강력 추천", "즉시 가능"}
    seen = set()
    for seed in range(60):
        title = TitleGenerator(opt, rng=random.Random(seed)).generate()
        for s in all_salts:
            if s in title:
                seen.add(s)
    # 충분한 시도 후 prefix/suffix 솔트가 모두 등장해야 함
    prefix_seen = seen & {"검증된", "전문"}
    suffix_seen = seen & {"강력 추천", "즉시 가능"}
    assert prefix_seen, f"중간 위치에서 prefix_salt가 한 번도 안 나옴 (seen={seen})"
    assert suffix_seen, f"중간 위치에서 suffix_salt가 한 번도 안 나옴 (seen={seen})"


@pytest.mark.unit
def test_subject_before_region_when_template_changed(regions_file, subjects_file, salts_file):
    """과목+지역+학습형태+솔트 템플릿: 과목이 지역보다 앞에 온다."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="과목+지역+학습형태+솔트",
    )
    regions  = {"대치동", "목동", "수원시"}
    subjects = {"영어", "수학", "국어"}
    title = TitleGenerator(opt, rng=random.Random(0)).generate()
    r = next(r for r in regions  if r in title)
    s = next(s for s in subjects if s in title)
    assert title.index(s) < title.index(r), f"과목이 지역 앞이어야 함: {title!r}"


# ===========================================================================
# 6. 제목에 모든 토큰 포함
# ===========================================================================

@pytest.mark.unit
def test_title_contains_region(gen):
    title   = gen.generate()
    regions = {"대치동", "목동", "수원시"}
    assert any(r in title for r in regions), f"지역 없음: {title!r}"


@pytest.mark.unit
def test_title_contains_subject(gen):
    title    = gen.generate()
    subjects = {"영어", "수학", "국어"}
    assert any(s in title for s in subjects), f"과목 없음: {title!r}"


@pytest.mark.unit
def test_title_contains_learning_type_gwaoe(gen):
    """학습형태(과외)가 항상 포함된다."""
    assert "과외" in gen.generate()


@pytest.mark.unit
def test_title_contains_learning_type_hakwon(regions_file, subjects_file, salts_file):
    """learning_type='학원'으로 변경하면 '학원'이 포함된다."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        learning_type="학원",
    )
    assert "학원" in TitleGenerator(opt, rng=random.Random(0)).generate()


@pytest.mark.unit
def test_title_contains_salt(gen):
    """기본 템플릿(솔트 마지막) → suffix_salts 중 하나가 포함된다."""
    title = gen.generate()
    suffix_salts = {"강력 추천", "즉시 가능"}
    assert any(s in title for s in suffix_salts), f"솔트 없음: {title!r}"


# ===========================================================================
# 7. 랜덤성
# ===========================================================================

@pytest.mark.unit
def test_generate_produces_varied_titles(option):
    """30번 호출하면 최소 2가지 이상의 서로 다른 제목이 나온다."""
    gen    = TitleGenerator(option)
    titles = {gen.generate() for _ in range(30)}
    assert len(titles) >= 2


@pytest.mark.unit
def test_fixed_seed_produces_same_title(option):
    """같은 시드 → 동일한 제목."""
    t1 = TitleGenerator(option, rng=random.Random(99)).generate()
    t2 = TitleGenerator(option, rng=random.Random(99)).generate()
    assert t1 == t2


# ===========================================================================
# 8. 스텁 기능 — 예외 없이 동작
# ===========================================================================


# ===========================================================================
# 9. TitleOption 기본값
# ===========================================================================


# ===========================================================================
# 10. fixed_title — 고정 제목 직접 지정
# ===========================================================================

@pytest.mark.unit
def test_fixed_title_bypasses_preset_lookup(option):
    """fixed_title이 설정되면 프리셋을 무시하고 그 문자열 그대로 반환한다."""
    opt = TitleOption(
        region_preset=str(option.region_preset),
        subject_preset=str(option.subject_preset),
        salt_preset=str(option.salt_preset),
        fixed_title="[테스트] 고정 제목",
    )
    title = TitleGenerator(opt, rng=random.Random(0)).generate()
    assert title == "[테스트] 고정 제목"


@pytest.mark.unit
def test_fixed_title_is_deterministic(option):
    """fixed_title은 시드나 호출 횟수에 무관하게 항상 동일하다."""
    opt = TitleOption(
        region_preset=str(option.region_preset),
        subject_preset=str(option.subject_preset),
        salt_preset=str(option.salt_preset),
        fixed_title="항상 이 제목",
    )
    titles = {TitleGenerator(opt, rng=random.Random(i)).generate() for i in range(20)}
    assert titles == {"항상 이 제목"}
