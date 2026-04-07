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

import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

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
    NewLineStep,
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
    NewLineBlock,
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
        logger.info("[build]   AI 텍스트 생성 중... (프롬프트: %s)", block.prompt[:80])
        text = ctx.text_gen.generate(block.prompt)
        logger.info("[build]   AI 텍스트 생성 완료 (%d자)", len(text))
        return [ParagraphStep(text=text, newlines=block.newlines, wait_ms=block.wait_ms)]


class TextHandler(BlockHandler):
    """TextBlock -> [TextStep]. 인라인 텍스트 또는 파일 읽기 — AI 없음."""

    def to_steps(self, block: TextBlock, ctx: ContentContext) -> list[PostStep]:
        if block.file:
            # 파일 모드
            path = Path(block.file)
            if not path.exists():
                raise FileNotFoundError(f"Text file not found: {path}")
            raw = path.read_text(encoding="utf-8")

            if block.format == "html":
                text = raw
            else:
                text = self._plain_to_html(raw)

            return [TextStep(text=text, is_html=(block.format == "html"), wait_ms=block.wait_ms)]

        # 인라인 모드 — content를 그대로 삽입
        return [TextStep(text=block.content, is_html=False, wait_ms=block.wait_ms)]

    @staticmethod
    def _plain_to_html(raw: str) -> str:
        """빈 줄 기준 <p> 분리, 단일 줄바꿈은 <br>."""
        paragraphs = []
        for chunk in raw.split("\n\n"):
            chunk = chunk.strip()
            if chunk:
                inner = chunk.replace("\n", "<br>")
                paragraphs.append(f"<p>{inner}</p>")
        return "\n".join(paragraphs)


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
            logger.info("[build]   이미지 처리 중: %s (%.1fKB)", Path(path).name, len(raw) / 1024)
            processed = ctx.img_proc.process(raw, block)
            name = _build_filename("preview", block.filename_keyword)
            path = _save_temp(processed, name, ctx)
            logger.info("[build]   이미지 처리 완료 → %s (%.1fKB)", Path(path).name, len(processed) / 1024)
        else:
            logger.warning("[build]   이미지 파일 없음: %s", path)
        return [ImageStep(path=path, link=block.link, wait_ms=block.wait_ms)]


class FeaturedImageHandler(BlockHandler):
    """FeaturedImageBlock -> [FeaturedImageStep]"""

    def to_steps(self, block: FeaturedImageBlock, ctx: ContentContext) -> list[PostStep]:
        path = block.path
        if Path(path).exists():
            raw = Path(block.path).read_bytes()
            logger.info("[build]   대표이미지 처리 중: %s (%.1fKB)", Path(path).name, len(raw) / 1024)
            processed = ctx.img_proc.process(raw, block)
            name = _build_filename("featured", block.filename_keyword)
            path = _save_temp(processed, name, ctx)
            logger.info("[build]   대표이미지 처리 완료 → %s (%.1fKB)", Path(path).name, len(processed) / 1024)
        else:
            logger.warning("[build]   대표이미지 파일 없음: %s", path)
        return [FeaturedImageStep(path=path, link=block.link, wait_ms=block.wait_ms)]


class HeadingHandler(BlockHandler):
    """HeadingBlock -> [HeadingStep]"""

    def to_steps(self, block: HeadingBlock, ctx: ContentContext) -> list[PostStep]:
        return [HeadingStep(level=block.level, text=block.text, wait_ms=block.wait_ms)]


class ListHandler(BlockHandler):
    """ListBlock -> [ListStep]"""

    def to_steps(self, block: ListBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.items:
            return []
        return [ListStep(items=block.items, ordered=block.ordered, wait_ms=block.wait_ms)]


class QuoteHandler(BlockHandler):
    """QuoteBlock -> [QuoteStep]"""

    def to_steps(self, block: QuoteBlock, ctx: ContentContext) -> list[PostStep]:
        if not block.text:
            return []
        text = block.text
        if block.attribution:
            text += f"\n— {block.attribution}"
        return [QuoteStep(text=text, type=block.type, wait_ms=block.wait_ms)]


class DividerHandler(BlockHandler):
    """DividerBlock -> [DividerStep]"""

    def to_steps(self, block: DividerBlock, ctx: ContentContext) -> list[PostStep]:
        return [DividerStep(type=block.type, wait_ms=block.wait_ms)]


class NewLineHandler(BlockHandler):
    """NewLineBlock -> [NewLineStep]"""

    def to_steps(self, block: NewLineBlock, ctx: ContentContext) -> list[PostStep]:
        return [NewLineStep(count=block.count, wait_ms=block.wait_ms)]


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
    NewLineBlock:       NewLineHandler(),
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
