"""
tests/test_layout_unit.py
--------------------------
Unit tests for layout alias parsing and validation.
"""

import pytest
from automator.options import ContentOption
from automator.layout import parse_alias, paragraph_count, validate_layout


# ===========================================================================
# 1. parse_alias
# ===========================================================================

@pytest.mark.unit
@pytest.mark.parametrize("alias, expected", [
    ("Image 1",     ("image",     1)),
    ("Image 3",     ("image",     3)),
    ("Thumbnail 1", ("thumbnail", 1)),
    ("Thumbnail 2", ("thumbnail", 2)),
    ("Paragraph 1", ("paragraph", 1)),
    ("Paragraph 5", ("paragraph", 5)),
])
def test_parse_alias_valid(alias, expected):
    assert parse_alias(alias) == expected


@pytest.mark.unit
@pytest.mark.parametrize("alias", [
    "image 1",       # 소문자
    "Image1",        # 공백 없음
    "Thumb 1",       # 잘못된 종류
    "Para 1",        # 잘못된 종류
    "",              # 빈 문자열
    "Image",         # 번호 없음
    "Paragraph 0",   # 0번은 valid parse지만 validate에서 거부
])
def test_parse_alias_invalid_pattern(alias):
    if alias == "Paragraph 0":
        # parse는 성공하지만 validate에서 거부 — 여기서는 parse만 테스트
        kind, n = parse_alias(alias)
        assert kind == "paragraph" and n == 0
    else:
        with pytest.raises(ValueError, match="Unknown layout alias"):
            parse_alias(alias)


# ===========================================================================
# 2. paragraph_count
# ===========================================================================

@pytest.mark.unit
def test_paragraph_count_basic():
    assert paragraph_count(["Paragraph 1", "Paragraph 2", "Paragraph 3"]) == 3


@pytest.mark.unit
def test_paragraph_count_with_mixed_aliases():
    layout = ["Image 1", "Paragraph 1", "Thumbnail 1", "Paragraph 2"]
    assert paragraph_count(layout) == 2


@pytest.mark.unit
def test_paragraph_count_empty_layout():
    assert paragraph_count([]) == 0


@pytest.mark.unit
def test_paragraph_count_no_paragraphs():
    assert paragraph_count(["Image 1", "Thumbnail 1"]) == 0


# ===========================================================================
# 3. validate_layout — 정상 케이스
# ===========================================================================

@pytest.mark.unit
def test_validate_empty_layout_is_valid():
    validate_layout(ContentOption())  # should not raise


@pytest.mark.unit
def test_validate_image_only_layout():
    opt = ContentOption(
        preview_images=["a.jpg", "b.jpg"],
        layout=["Image 1", "Image 2"],
    )
    validate_layout(opt)


@pytest.mark.unit
def test_validate_full_layout():
    opt = ContentOption(
        preview_images=["a.jpg", "b.jpg"],
        thumbnail_images=["thumb.jpg"],
        layout=["Image 1", "Paragraph 1", "Thumbnail 1",
                "Image 2", "Paragraph 2", "Paragraph 3"],
    )
    validate_layout(opt)


@pytest.mark.unit
def test_validate_thumbnail_first_layout():
    opt = ContentOption(
        thumbnail_images=["thumb.jpg"],
        layout=["Thumbnail 1", "Paragraph 1"],
    )
    validate_layout(opt)


# ===========================================================================
# 4. validate_layout — 오류 케이스
# ===========================================================================

@pytest.mark.unit
def test_validate_raises_on_unknown_alias():
    with pytest.raises(ValueError, match="Unknown layout alias"):
        validate_layout(ContentOption(layout=["Unknown 1"]))


@pytest.mark.unit
def test_validate_raises_on_image_out_of_range():
    with pytest.raises(ValueError, match="Image 2"):
        validate_layout(ContentOption(
            preview_images=["a.jpg"],
            layout=["Image 1", "Image 2"],
        ))


@pytest.mark.unit
def test_validate_raises_on_thumbnail_out_of_range():
    with pytest.raises(ValueError, match="Thumbnail 1"):
        validate_layout(ContentOption(
            layout=["Thumbnail 1"],  # thumbnail_images=[]
        ))


@pytest.mark.unit
def test_validate_raises_on_duplicate_image_alias():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_layout(ContentOption(
            preview_images=["a.jpg"],
            layout=["Image 1", "Image 1"],
        ))


@pytest.mark.unit
def test_validate_raises_on_duplicate_paragraph_alias():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_layout(ContentOption(
            layout=["Paragraph 1", "Paragraph 1"],
        ))


@pytest.mark.unit
def test_validate_raises_on_paragraph_gap():
    # Paragraph 2 없이 1, 3 — gap
    with pytest.raises(ValueError, match="contiguous"):
        validate_layout(ContentOption(
            layout=["Paragraph 1", "Paragraph 3"],
        ))


@pytest.mark.unit
def test_validate_raises_on_paragraph_not_starting_from_one():
    with pytest.raises(ValueError, match="contiguous"):
        validate_layout(ContentOption(
            layout=["Paragraph 2"],
        ))


@pytest.mark.unit
def test_validate_raises_on_zero_index():
    # "Paragraph 0" — index < 1
    with pytest.raises(ValueError, match=">= 1"):
        validate_layout(ContentOption(
            layout=["Paragraph 0"],
        ))


# ===========================================================================
# 5. paragraph_count reflects layout
# ===========================================================================

@pytest.mark.unit
def test_paragraph_count_matches_layout_max():
    layout = ["Image 1", "Paragraph 1", "Thumbnail 1",
              "Paragraph 2", "Paragraph 3"]
    assert paragraph_count(layout) == 3


@pytest.mark.unit
def test_paragraph_count_single():
    assert paragraph_count(["Paragraph 1"]) == 1
