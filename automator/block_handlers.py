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
    TextStep,
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
    TextBlock,
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
    tmp_files: list[str]  = field(default_factory=list)
    text_gen:  Any        = None
    img_proc:  Any        = None


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
        text = ctx.text_gen.generate(block.prompt)
        return [ParagraphStep(text=text, newlines=block.newlines)]


class TextHandler(BlockHandler):
    """TextBlock -> [TextStep]. 외부 파일 읽기 — AI 없음."""

    def to_steps(self, block: TextBlock, ctx: ContentContext) -> list[PostStep]:
        path = Path(block.file)
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")
        raw = path.read_text(encoding="utf-8")

        if block.format == "html":
            text = raw
        else:
            # plain: 빈 줄 기준으로 <p> 분리, 단일 줄바꿈은 <br>
            paragraphs = []
            for chunk in raw.split("\n\n"):
                chunk = chunk.strip()
                if chunk:
                    inner = chunk.replace("\n", "<br>")
                    paragraphs.append(f"<p>{inner}</p>")
            text = "\n".join(paragraphs)

        return [TextStep(text=text, is_html=(block.format == "html"))]


def _build_filename(role: str, keyword: str) -> str:
    """Build an upload filename from role and keyword."""
    if keyword:
        return f"{keyword}-{role}.jpg"
    return f"{role}.jpg"


def _save_temp(data: bytes, name: str, ctx: ContentContext) -> str:
    """Write data to a temp file and register it for cleanup."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".jpg", prefix=name.replace(".jpg", "_"), delete=False,
    )
    tmp.write(data)
    tmp.close()
    ctx.tmp_files.append(tmp.name)
    return tmp.name


class ImageHandler(BlockHandler):
    """ImageBlock -> [ImageStep]"""

    def to_steps(self, block: ImageBlock, ctx: ContentContext) -> list[PostStep]:
        path = block.path
        if Path(path).exists():
            raw = Path(block.path).read_bytes()
            processed = ctx.img_proc.process(raw, block)
            name = _build_filename("preview", block.filename_keyword)
            path = _save_temp(processed, name, ctx)
        return [ImageStep(path=path, link=block.link)]


class FeaturedImageHandler(BlockHandler):
    """FeaturedImageBlock -> [FeaturedImageStep]"""

    def to_steps(self, block: FeaturedImageBlock, ctx: ContentContext) -> list[PostStep]:
        path = block.path
        if Path(path).exists():
            raw = Path(block.path).read_bytes()
            processed = ctx.img_proc.process(raw, block)
            name = _build_filename("featured", block.filename_keyword)
            path = _save_temp(processed, name, ctx)
        return [FeaturedImageStep(path=path, link=block.link)]


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
    TextBlock:          TextHandler(),
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
