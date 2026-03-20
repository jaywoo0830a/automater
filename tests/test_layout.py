"""
tests/test_layout.py — Section/Block validation.
"""

import pytest
from automator.options import (
    ParagraphBlock, ImageBlock, FeaturedImageBlock,
    HeadingBlock, ListBlock, QuoteBlock, DividerBlock,
    Section,
)
from automator.layout import validate_sections, paragraph_block_count, all_blocks


def _section(*blocks):
    return Section(blocks=tuple(blocks))


@pytest.mark.unit
def test_empty_sections_valid():
    validate_sections([])


@pytest.mark.unit
def test_empty_section_valid():
    validate_sections([_section()])


@pytest.mark.unit
def test_single_featured_valid():
    validate_sections([_section(
        ImageBlock(path="a.jpg"),
        FeaturedImageBlock(path="t.jpg"),
        ParagraphBlock(),
    )])


@pytest.mark.unit
def test_two_featured_raises():
    with pytest.raises(ValueError, match="FeaturedImageBlock"):
        validate_sections([_section(
            FeaturedImageBlock(path="a.jpg"),
            FeaturedImageBlock(path="b.jpg"),
        )])


@pytest.mark.unit
def test_two_featured_across_sections_raises():
    """FeaturedImageBlock 은 섹션에 걸쳐서도 최대 1개여야 한다."""
    with pytest.raises(ValueError, match="FeaturedImageBlock"):
        validate_sections([
            _section(FeaturedImageBlock(path="a.jpg")),
            _section(FeaturedImageBlock(path="b.jpg")),
        ])


@pytest.mark.unit
def test_paragraph_block_count():
    sections = [
        _section(ParagraphBlock(), ImageBlock(path="x.jpg")),
        _section(ParagraphBlock(), FeaturedImageBlock(path="y.jpg")),
    ]
    assert paragraph_block_count(sections) == 2


@pytest.mark.unit
def test_paragraph_block_count_zero():
    assert paragraph_block_count([_section(ImageBlock(path="a.jpg"))]) == 0


@pytest.mark.unit
def test_all_blocks_flattens_sections():
    b1, b2, b3 = ParagraphBlock(), ImageBlock(path="a.jpg"), DividerBlock()
    sections = [_section(b1, b2), _section(b3)]
    assert all_blocks(sections) == [b1, b2, b3]


@pytest.mark.unit
def test_all_block_types_accepted():
    """7종 Block 이 모두 validate_sections 를 통과해야 한다."""
    validate_sections([_section(
        HeadingBlock(level=2, text="제목"),
        ParagraphBlock(prompt="본문"),
        ImageBlock(path="img.jpg"),
        FeaturedImageBlock(path="thumb.jpg"),
        ListBlock(items=("항목1", "항목2")),
        QuoteBlock(text="인용", attribution="출처"),
        DividerBlock(),
    )])
