"""
Unit tests for layout.py (Block validation utilities).
"""

import pytest
from automator.options import TextBlock, ImageBlock, FeaturedBlock
from automator.layout import validate_blocks, text_block_count


@pytest.mark.unit
def test_empty_blocks_valid():
    validate_blocks([])


@pytest.mark.unit
def test_single_featured_valid():
    validate_blocks([ImageBlock("a.jpg"), FeaturedBlock("t.jpg"), TextBlock()])


@pytest.mark.unit
def test_two_featured_raises():
    with pytest.raises(ValueError, match="FeaturedBlock"):
        validate_blocks([FeaturedBlock("a.jpg"), FeaturedBlock("b.jpg")])


@pytest.mark.unit
def test_text_block_count():
    blocks = [TextBlock(), ImageBlock("x.jpg"), TextBlock(), FeaturedBlock("y.jpg")]
    assert text_block_count(blocks) == 2


@pytest.mark.unit
def test_text_block_count_zero():
    assert text_block_count([ImageBlock("a.jpg")]) == 0
