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
    data = {"salts": ["강력 추천", "즉시 가능"]}
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
def test_load_salts_returns_list(salts_file):
    assert "강력 추천" in load_salts(salts_file)


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
def test_salt_at_end_by_default(gen):
    """기본 템플릿: 솔트('강력 추천' or '즉시 가능')가 맨 끝에 온다."""
    for seed in range(20):
        title = TitleGenerator(gen._opt, rng=random.Random(seed)).generate()
        salts = {"강력 추천", "즉시 가능"}
        assert any(title.endswith(s) for s in salts), f"솔트가 맨 끝 아님: {title!r}"


@pytest.mark.unit
def test_salt_at_front_when_template_changed(regions_file, subjects_file, salts_file):
    """솔트+지역+과목+학습형태 템플릿: 솔트가 맨 앞에 온다."""
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        template="솔트+지역+과목+학습형태",
    )
    salts = {"강력 추천", "즉시 가능"}
    for seed in range(20):
        title = TitleGenerator(opt, rng=random.Random(seed)).generate()
        assert any(title.startswith(s) for s in salts), f"솔트가 맨 앞 아님: {title!r}"


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
    title = gen.generate()
    salts = {"강력 추천", "즉시 가능"}
    assert any(s in title for s in salts), f"솔트 없음: {title!r}"


@pytest.mark.unit
def test_title_is_non_empty_string(gen):
    assert isinstance(gen.generate(), str)
    assert len(gen.generate()) > 0


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

@pytest.mark.unit
def test_add_affix_stub_does_not_raise(regions_file, subjects_file, salts_file):
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        add_affix=True,
    )
    title = TitleGenerator(opt, rng=random.Random(0)).generate()
    assert isinstance(title, str) and len(title) > 0


@pytest.mark.unit
def test_randomize_chars_stub_does_not_raise(regions_file, subjects_file, salts_file):
    opt = TitleOption(
        region_preset=str(regions_file),
        subject_preset=str(subjects_file),
        salt_preset=str(salts_file),
        randomize_chars=True,
    )
    title = TitleGenerator(opt, rng=random.Random(0)).generate()
    assert isinstance(title, str) and len(title) > 0


# ===========================================================================
# 9. TitleOption 기본값
# ===========================================================================

@pytest.mark.unit
def test_title_option_default_template():
    assert TitleOption().template == "지역+과목+학습형태+솔트"


@pytest.mark.unit
def test_title_option_default_learning_type():
    assert TitleOption().learning_type == "과외"


@pytest.mark.unit
def test_title_option_default_include_suffix():
    assert TitleOption().include_suffix is True


@pytest.mark.unit
def test_title_option_stubs_are_off_by_default():
    opt = TitleOption()
    assert opt.add_affix is False
    assert opt.randomize_chars is False
    assert opt.ai_preset_prompt == ""


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


@pytest.mark.unit
def test_empty_fixed_title_falls_back_to_generator(option):
    """fixed_title이 빈 문자열이면 TitleGenerator가 정상 동작한다."""
    opt = TitleOption(
        region_preset=str(option.region_preset),
        subject_preset=str(option.subject_preset),
        salt_preset=str(option.salt_preset),
        fixed_title="",  # 기본값 — 프리셋 생성 사용
    )
    title = TitleGenerator(opt, rng=random.Random(42)).generate()
    assert len(title) > 0
    assert title != ""


@pytest.mark.unit
def test_title_option_fixed_title_default_is_empty():
    """fixed_title 기본값은 빈 문자열이다."""
    assert TitleOption().fixed_title == ""
