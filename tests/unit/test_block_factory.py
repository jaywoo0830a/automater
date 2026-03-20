"""
tests/unit/test_block_factory.py
-----------------------------------
BlockFactory — block_type string → Block dataclass with interpolation.
"""

import pytest

from automator.block_factory import create_block, FACTORIES
from automator.options import (
    ParagraphBlock, ImageBlock, FeaturedImageBlock,
    HeadingBlock, ListBlock, QuoteBlock, DividerBlock,
)


# ---------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_all_block_types_registered():
    """Every concrete Block type has a factory entry."""
    assert "paragraph" in FACTORIES
    assert "image" in FACTORIES
    assert "featured" in FACTORIES
    assert "heading" in FACTORIES
    assert "list" in FACTORIES
    assert "quote" in FACTORIES
    assert "divider" in FACTORIES


@pytest.mark.unit
def test_unknown_type_raises():
    with pytest.raises(KeyError, match="unknown_type"):
        create_block("unknown_type", {})


# ---------------------------------------------------------------------------
# Basic creation (no interpolation)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_paragraph_from_config():
    block = create_block("paragraph", {"prompt": "test prompt", "tone": "review"})
    assert isinstance(block, ParagraphBlock)
    assert block.prompt == "test prompt"
    assert block.tone == "review"


@pytest.mark.unit
def test_heading_from_config():
    block = create_block("heading", {"level": 2, "text": "Section title"})
    assert isinstance(block, HeadingBlock)
    assert block.level == 2
    assert block.text == "Section title"


@pytest.mark.unit
def test_image_from_config():
    block = create_block("image", {"path": "/tmp/a.jpg", "alt": "photo"})
    assert isinstance(block, ImageBlock)
    assert block.path == "/tmp/a.jpg"


@pytest.mark.unit
def test_featured_from_config():
    block = create_block("featured", {"path": "/tmp/b.jpg", "overlay_text": "text"})
    assert isinstance(block, FeaturedImageBlock)


@pytest.mark.unit
def test_list_from_config():
    block = create_block("list", {"items": ("a", "b"), "ordered": True})
    assert isinstance(block, ListBlock)
    assert block.ordered is True


@pytest.mark.unit
def test_quote_from_config():
    block = create_block("quote", {"text": "wisdom", "attribution": "author"})
    assert isinstance(block, QuoteBlock)


@pytest.mark.unit
def test_divider_from_empty_config():
    block = create_block("divider", {})
    assert isinstance(block, DividerBlock)


# ---------------------------------------------------------------------------
# Placeholder interpolation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_keyword_placeholder():
    """'{keyword}' in config is replaced with the full keyword string."""
    block = create_block(
        "paragraph",
        {"keyword": "{keyword}", "tone": "review"},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.keyword == "강남 수학"


@pytest.mark.unit
def test_slug_placeholder():
    """'{region}' is replaced with the value for that slug."""
    block = create_block(
        "heading",
        {"level": 2, "text": "{region} {subject} guide"},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.text == "강남 수학 guide"


@pytest.mark.unit
def test_mixed_placeholders():
    """Multiple placeholder types in the same value."""
    block = create_block(
        "paragraph",
        {"prompt": "{region}에서 {keyword} 홍보"},
        values={"region": "강남"},
        keyword="강남 수학",
    )
    assert block.prompt == "강남에서 강남 수학 홍보"


@pytest.mark.unit
def test_unresolved_placeholder_preserved():
    """Unknown placeholder like {unknown} stays as-is."""
    block = create_block(
        "heading",
        {"level": 1, "text": "{unknown} title"},
        values={"region": "강남"},
        keyword="강남",
    )
    assert block.text == "{unknown} title"


@pytest.mark.unit
def test_non_string_values_unchanged():
    """Non-string config values pass through without interpolation."""
    block = create_block(
        "paragraph",
        {"prompt": "test", "min_chars": 250, "max_chars": 500},
    )
    assert block.min_chars == 250
    assert block.max_chars == 500


# ---------------------------------------------------------------------------
# Unknown config keys are ignored (forward compatibility)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_unknown_config_keys_ignored():
    """Keys not in the dataclass are silently dropped."""
    block = create_block(
        "paragraph",
        {"prompt": "test", "future_field": "ignored"},
    )
    assert isinstance(block, ParagraphBlock)
    assert block.prompt == "test"


@pytest.mark.unit
def test_list_interpolation():
    """Placeholders inside list items are also interpolated."""
    block = create_block(
        "featured",
        {"path": "/img.jpg", "overlay_text": ["{region}", "{subject}"]},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.overlay_text == ["강남", "수학"]
