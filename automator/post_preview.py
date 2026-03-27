"""
automator/post_preview.py
----------------------------
Dry-run post preview — no Gemini calls, no image processing.

Shows what a post would look like with a given title option
and sections, producing placeholder descriptions for each block.

SPA workflow Step 3: user selects a template, sees a preview
of title + block outline before committing to execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from automator.options import (
    Block,
    TitleOption,
    Section,
    HeadingBlock,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
)
from automator.title_generator import generate_title


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlockPreview:
    """Preview of one block in the post body."""
    block_type:  str
    placeholder: str


@dataclass(frozen=True)
class PostPreview:
    """Preview of a complete post."""
    sample_title: str
    blocks:       list[BlockPreview]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preview_post(
    title_option: TitleOption | str,
    sections: tuple[Section, ...],
) -> PostPreview:
    """
    Generate a dry-run preview of a post.

    Args:
        title_option: TitleOption for template-based generation, or a plain str.
        sections:     Tuple of Sections defining the post body layout.

    Returns:
        PostPreview with sample title and block-level placeholders.
    """
    sample_title = title_option if isinstance(title_option, str) else generate_title(title_option)

    blocks: list[BlockPreview] = []
    for section in sections:
        for block in section.blocks:
            blocks.append(_preview_block(block))

    return PostPreview(sample_title=sample_title, blocks=blocks)


# ---------------------------------------------------------------------------
# Block preview dispatch
# ---------------------------------------------------------------------------

_BLOCK_PREVIEWS: dict[type, callable] = {}


def _preview_block(block: Block) -> BlockPreview:
    """Dispatch to the appropriate preview function for a block type."""
    preview_fn = _BLOCK_PREVIEWS.get(type(block))
    if preview_fn is None:
        return BlockPreview(
            block_type=type(block).__name__,
            placeholder="[unknown block type]",
        )
    return preview_fn(block)


def _register(block_type: type):
    """Decorator to register a preview function for a block type."""
    def decorator(fn):
        _BLOCK_PREVIEWS[block_type] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Concrete preview functions — one per block type
# ---------------------------------------------------------------------------

@_register(ParagraphBlock)
def _preview_paragraph(block: ParagraphBlock) -> BlockPreview:
    if block.prompt:
        desc = f"[AI paragraph: {block.prompt}]"
    else:
        desc = "[AI-generated paragraph]"
    return BlockPreview(block_type="paragraph", placeholder=desc)


@_register(HeadingBlock)
def _preview_heading(block: HeadingBlock) -> BlockPreview:
    return BlockPreview(
        block_type="heading",
        placeholder=f"[H{block.level}] {block.text}",
    )


@_register(ImageBlock)
def _preview_image(block: ImageBlock) -> BlockPreview:
    filename = PurePosixPath(block.path).name if block.path else "no file"
    return BlockPreview(
        block_type="image",
        placeholder=f"[Body image: {filename}]",
    )


@_register(FeaturedImageBlock)
def _preview_featured(block: FeaturedImageBlock) -> BlockPreview:
    filename = PurePosixPath(block.path).name if block.path else "no file"
    overlay = f", overlay: '{block.overlay_text}'" if block.overlay_text else ""
    return BlockPreview(
        block_type="featured",
        placeholder=f"[Featured image: {filename}{overlay}]",
    )


@_register(ListBlock)
def _preview_list(block: ListBlock) -> BlockPreview:
    style = "ordered" if block.ordered else "unordered"
    return BlockPreview(
        block_type="list",
        placeholder=f"[{style} list, {len(block.items)} items]",
    )


@_register(QuoteBlock)
def _preview_quote(block: QuoteBlock) -> BlockPreview:
    attr = f" — {block.attribution}" if block.attribution else ""
    text = block.text[:40] + "..." if len(block.text) > 40 else block.text
    return BlockPreview(
        block_type="quote",
        placeholder=f"[Quote: {text}{attr}]",
    )


@_register(DividerBlock)
def _preview_divider(block: DividerBlock) -> BlockPreview:
    return BlockPreview(block_type="divider", placeholder="[---]")
