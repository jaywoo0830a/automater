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

def test_all_block_types_registered():
    """Every concrete Block type has a factory entry."""
    assert "paragraph" in FACTORIES
    assert "image" in FACTORIES
    assert "featured_image" in FACTORIES
    assert "heading" in FACTORIES
    assert "list" in FACTORIES
    assert "quote" in FACTORIES
    assert "divider" in FACTORIES


def test_unknown_type_raises():
    with pytest.raises(KeyError, match="unknown_type"):
        create_block("unknown_type", {})


# ---------------------------------------------------------------------------
# Basic creation (no interpolation)
# ---------------------------------------------------------------------------

def test_paragraph_from_config():
    block = create_block("paragraph", {"prompt": "test prompt"})
    assert isinstance(block, ParagraphBlock)
    assert block.prompt == "test prompt"


def test_heading_from_config():
    block = create_block("heading", {"level": 2, "text": "Section title"})
    assert isinstance(block, HeadingBlock)
    assert block.level == 2
    assert block.text == "Section title"


def test_image_from_config():
    block = create_block("image", {"path": "/tmp/a.jpg", "alt": "photo"})
    assert isinstance(block, ImageBlock)
    assert block.path == "/tmp/a.jpg"


def test_featured_from_config():
    block = create_block("featured_image", {"path": "/tmp/b.jpg", "overlay_text": "text"})
    assert isinstance(block, FeaturedImageBlock)


def test_list_from_config():
    block = create_block("list", {"items": ("a", "b"), "ordered": True})
    assert isinstance(block, ListBlock)
    assert block.ordered is True


def test_quote_from_config():
    block = create_block("quote", {"text": "wisdom", "attribution": "author"})
    assert isinstance(block, QuoteBlock)


def test_divider_from_empty_config():
    block = create_block("divider", {})
    assert isinstance(block, DividerBlock)


# ---------------------------------------------------------------------------
# Placeholder interpolation
# ---------------------------------------------------------------------------

def test_keyword_placeholder():
    """'{keyword}' in config is replaced with the full keyword string."""
    block = create_block(
        "paragraph",
        {"prompt": "{keyword} 과외를 소개해줘"},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.prompt == "강남 수학 과외를 소개해줘"


def test_slug_placeholder():
    """'{region}' is replaced with the value for that slug."""
    block = create_block(
        "heading",
        {"level": 2, "text": "{region} {subject} guide"},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.text == "강남 수학 guide"


def test_mixed_placeholders():
    """Multiple placeholder types in the same value."""
    block = create_block(
        "paragraph",
        {"prompt": "{region}에서 {keyword} 홍보"},
        values={"region": "강남"},
        keyword="강남 수학",
    )
    assert block.prompt == "강남에서 강남 수학 홍보"


def test_unresolved_placeholder_preserved():
    """Unknown placeholder like {unknown} stays as-is."""
    block = create_block(
        "heading",
        {"level": 1, "text": "{unknown} title"},
        values={"region": "강남"},
        keyword="강남",
    )
    assert block.text == "{unknown} title"


def test_non_string_values_unchanged():
    """Non-string config values pass through without interpolation."""
    block = create_block(
        "paragraph",
        {"prompt": "test", "newlines": 3},
    )
    assert block.newlines == 3


# ---------------------------------------------------------------------------
# Unknown config keys are ignored (forward compatibility)
# ---------------------------------------------------------------------------

def test_unknown_config_keys_ignored():
    """Keys not in the dataclass are silently dropped."""
    block = create_block(
        "paragraph",
        {"prompt": "test", "future_field": "ignored"},
    )
    assert isinstance(block, ParagraphBlock)
    assert block.prompt == "test"


def test_list_interpolation():
    """Placeholders inside list items are also interpolated."""
    block = create_block(
        "featured_image",
        {"path": "/img.jpg", "overlay_text": ["{region}", "{subject}"]},
        values={"region": "강남", "subject": "수학"},
        keyword="강남 수학",
    )
    assert block.overlay_text == ["강남", "수학"]


# ---------------------------------------------------------------------------
# media_id resolution
# ---------------------------------------------------------------------------

def test_image_media_id_resolved_to_path():
    """media_id in config is resolved to path via resolver."""
    resolver = lambda mid: f"/uploads/{mid}/photo.jpg"
    block = create_block(
        "image",
        {"media_id": 42},
        media_resolver=resolver,
    )
    assert isinstance(block, ImageBlock)
    assert block.path == "/uploads/42/photo.jpg"


def test_featured_media_id_with_overlay():
    """Featured block resolves media_id and keeps overlay_text."""
    resolver = lambda mid: f"/uploads/{mid}/thumb.jpg"
    block = create_block(
        "featured_image",
        {"media_id": 7, "overlay_text": "{keyword}"},
        values={"region": "강남"},
        keyword="강남 수학",
        media_resolver=resolver,
    )
    assert isinstance(block, FeaturedImageBlock)
    assert block.path == "/uploads/7/thumb.jpg"
    assert block.overlay_text == "강남 수학"


def test_media_id_without_resolver_raises():
    """media_id present but no resolver → ValueError."""
    with pytest.raises(ValueError, match="media_resolver"):
        create_block("image", {"media_id": 1})


def test_media_id_stripped_from_config():
    """media_id itself is not passed to the Block dataclass."""
    resolver = lambda mid: "/resolved.jpg"
    block = create_block("image", {"media_id": 1}, media_resolver=resolver)
    assert not hasattr(block, "media_id")
    assert block.path == "/resolved.jpg"


def test_path_takes_precedence_over_media_id():
    """Explicit path in config is used even if media_id is present."""
    resolver = lambda mid: "/resolved.jpg"
    block = create_block(
        "image",
        {"path": "/explicit.jpg", "media_id": 99},
        media_resolver=resolver,
    )
    assert block.path == "/explicit.jpg"


def test_non_image_block_ignores_media_id():
    """media_id in non-image block is filtered out by _filter_fields."""
    block = create_block(
        "paragraph",
        {"prompt": "text", "media_id": 5},
        media_resolver=lambda mid: "/x.jpg",
    )
    assert isinstance(block, ParagraphBlock)
    assert block.prompt == "text"
