"""
automator/block_handlers.py
-----------------------------
BlockHandler ABC + concrete handlers + HANDLERS registry.

Naming convention: XxxBlock -> XxxHandler -> XxxStep

Adding a new Block type:
    1. Define the Block dataclass in options.py
    2. Define the PostStep subclass in editor.py (if new primitive needed)
    3. Write a BlockHandler subclass here
    4. Register it in HANDLERS
"""

from __future__ import annotations

import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from automator.editor import (
    PostStep,
    ParagraphStep,
    ImageStep,
    FeaturedImageStep,
    HeadingStep,
    ListStep,
    QuoteStep,
    DividerStep,
)
from automator.options import (
    Block,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
)

if TYPE_CHECKING:
    from automator.ports import TextGenerator, ImageProcessor


# ---------------------------------------------------------------------------
# ContentContext
# ---------------------------------------------------------------------------

@dataclass
class ContentContext:
    """Mutable context shared across handlers during content generation."""
    paragraph_index:  int        = 0
    total_paragraphs: int        = 0
    tmp_files:        list[str]  = field(default_factory=list)
    text_gen:         Any        = None
    img_proc:         Any        = None


# ---------------------------------------------------------------------------
# BlockHandler ABC
# ---------------------------------------------------------------------------

class BlockHandler(ABC):
    """
    Converts a Block into PostStep(s).

    SRP: one handler = one block type's conversion rules.
    LSP: any handler is substitutable through to_steps().
    """

    @abstractmethod
    def to_steps(self, block: Block, ctx: ContentContext) -> list[PostStep]:
        """Convert block into PostStep(s)."""


# ---------------------------------------------------------------------------
# Concrete handlers
# ---------------------------------------------------------------------------

class ParagraphHandler(BlockHandler):
    """ParagraphBlock -> [ParagraphStep]"""

    def to_steps(self, block: ParagraphBlock, ctx: ContentContext) -> list[PostStep]:
        from automator.seo_prompt import build_prompt

        prompt = build_prompt(
            block,
            paragraph_index=ctx.paragraph_index,
            total_paragraphs=ctx.total_paragraphs,
        )
        text = ctx.text_gen.generate(prompt, 1)[0]
        ctx.paragraph_index += 1
        return [ParagraphStep(text=text, newlines=block.newlines)]


class ImageHandler(BlockHandler):
    """ImageBlock -> [ImageStep]"""

    def to_steps(self, block: ImageBlock, ctx: ContentContext) -> list[PostStep]:
        path = block.path
        if Path(path).exists():
            path = self._process(block, ctx)
        return [ImageStep(path=path)]

    def _process(self, block: ImageBlock, ctx: ContentContext) -> str:
        raw = Path(block.path).read_bytes()
        processed = ctx.img_proc.process_body(raw, block)
        fname = ctx.img_proc.build_filename("preview", 1, block.filename_keyword)
        tmp = tempfile.NamedTemporaryFile(
            suffix=".jpg", prefix=fname.replace(".jpg", "_"), delete=False,
        )
        tmp.write(processed)
        tmp.close()
        ctx.tmp_files.append(tmp.name)
        return tmp.name


class FeaturedImageHandler(BlockHandler):
    """FeaturedImageBlock -> [FeaturedImageStep]"""

    def to_steps(self, block: FeaturedImageBlock, ctx: ContentContext) -> list[PostStep]:
        path = block.path
        if Path(path).exists():
            path = self._process(block, ctx)
        return [FeaturedImageStep(path=path)]

    def _process(self, block: FeaturedImageBlock, ctx: ContentContext) -> str:
        raw = Path(block.path).read_bytes()
        processed = ctx.img_proc.process_featured(raw, block)
        fname = ctx.img_proc.build_filename("featured", 1, block.filename_keyword)
        tmp = tempfile.NamedTemporaryFile(
            suffix=".jpg", prefix=fname.replace(".jpg", "_"), delete=False,
        )
        tmp.write(processed)
        tmp.close()
        ctx.tmp_files.append(tmp.name)
        return tmp.name


class HeadingHandler(BlockHandler):
    """HeadingBlock -> [HeadingStep]"""

    def to_steps(self, block: HeadingBlock, ctx: ContentContext) -> list[PostStep]:
        return [HeadingStep(level=block.level, text=block.text)]


class ListHandler(BlockHandler):
    """ListBlock -> [ListStep]"""

    def to_steps(self, block: ListBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.items:
            return []
        lines = []
        for i, item in enumerate(block.items, 1):
            prefix = f"{i}. " if block.ordered else "- "
            lines.append(f"{prefix}{item}")
        return [ListStep(text="\n".join(lines))]


class QuoteHandler(BlockHandler):
    """QuoteBlock -> [QuoteStep]"""

    def to_steps(self, block: QuoteBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.text:
            return []
        text = block.text
        if block.attribution:
            text += f"\n— {block.attribution}"
        return [QuoteStep(text=text)]


class DividerHandler(BlockHandler):
    """DividerBlock -> [DividerStep]"""

    def to_steps(self, block: DividerBlock, ctx: ContentContext) -> list[PostStep]:
        return [DividerStep()]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

HANDLERS: dict[type[Block], BlockHandler] = {
    ParagraphBlock:     ParagraphHandler(),
    ImageBlock:         ImageHandler(),
    FeaturedImageBlock: FeaturedImageHandler(),
    HeadingBlock:       HeadingHandler(),
    ListBlock:          ListHandler(),
    QuoteBlock:         QuoteHandler(),
    DividerBlock:       DividerHandler(),
}


def get_handler(block: Block) -> BlockHandler:
    """Look up the handler for a block. Raises KeyError if unregistered."""
    block_type = type(block)
    if block_type not in HANDLERS:
        raise KeyError(
            f"No BlockHandler registered for {block_type.__name__}. "
            f"Register one in HANDLERS."
        )
    return HANDLERS[block_type]
