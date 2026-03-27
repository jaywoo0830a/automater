"""
tests/test_layout.py — Section/Block validation.
"""

import pytest
from automator.options import (
    ParagraphBlock, ImageBlock, FeaturedImageBlock,
    HeadingBlock, ListBlock, QuoteBlock, DividerBlock,
    Section,
)
from automator.layout import validate_sections, all_blocks


def _section(*blocks):
    return Section(blocks=tuple(blocks))


def test_empty_sections_valid():
    validate_sections([])


def test_empty_section_valid():
    validate_sections([_section()])


def test_single_featured_valid():
    validate_sections([_section(
        ImageBlock(path="a.jpg"),
        FeaturedImageBlock(path="t.jpg"),
        ParagraphBlock(),
    )])


def test_two_featured_raises():
    with pytest.raises(ValueError, match="FeaturedImageBlock"):
        validate_sections([_section(
            FeaturedImageBlock(path="a.jpg"),
            FeaturedImageBlock(path="b.jpg"),
        )])


def test_two_featured_across_sections_raises():
    """FeaturedImageBlock 은 섹션에 걸쳐서도 최대 1개여야 한다."""
    with pytest.raises(ValueError, match="FeaturedImageBlock"):
        validate_sections([
            _section(FeaturedImageBlock(path="a.jpg")),
            _section(FeaturedImageBlock(path="b.jpg")),
        ])




def test_all_blocks_flattens_sections():
    b1, b2, b3 = ParagraphBlock(), ImageBlock(path="a.jpg"), DividerBlock()
    sections = [_section(b1, b2), _section(b3)]
    assert all_blocks(sections) == [b1, b2, b3]


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
