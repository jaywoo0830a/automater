"""
automator/content_builder.py
------------------------------
ContentBuilder — converts a PostingSpec into executable PostSteps.

Depends on TextGenerator and ImageProcessor ABCs (ports), never on
concrete implementations. Concrete instances are injected in __init__.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from automator.contracts import PostingSpec
from automator.editor import PostStep, ParagraphStep, _PostContent
from automator.block_handlers import ContentContext, get_handler
from automator.layout import all_blocks
from automator.ports import TextGenerator, ImageProcessor
from automator.title_generator import generate_title

logger = logging.getLogger(__name__)


class ContentBuilder:
    """
    Transform a PostingSpec into _PostContent (title + steps + schedule).

    Injected dependencies:
        text_gen  — generates paragraph text from prompts
        img_proc  — processes raw image bytes
    """

    def __init__(
        self,
        text_gen: TextGenerator,
        img_proc: ImageProcessor,
    ) -> None:
        self._text_gen = text_gen
        self._img_proc = img_proc

    def build(self, spec: PostingSpec) -> _PostContent:
        """Convert spec into _PostContent with title, steps, tags, schedule."""
        title = spec.title if isinstance(spec.title, str) else generate_title(spec.title)
        flat_blocks = all_blocks(list(spec.body))

        logger.info("[build] 블록 %d개 처리 시작", len(flat_blocks))

        if not flat_blocks:
            logger.info("[build] 블록 없음 — 기본 텍스트 생성")
            stub = self._text_gen.generate("")
            return _PostContent(
                title=title,
                steps=[ParagraphStep(text=stub, newlines=2)],
                tags=spec.publish.tags,
                visibility=spec.publish.visibility,
                schedule_at=spec.schedule_at,
                align=spec.align,
            )

        ctx = ContentContext(
            text_gen=self._text_gen,
            img_proc=self._img_proc,
        )

        steps_out: list[PostStep] = []
        for i, block in enumerate(flat_blocks):
            block_name = type(block).__name__
            handler = get_handler(block)
            logger.info("[build] [%d/%d] %s 변환 중...", i + 1, len(flat_blocks), block_name)
            try:
                new_steps = handler.to_steps(block, ctx)
            except Exception as exc:
                # 어느 블록에서 실패했는지 명확히 남긴다
                logger.error(
                    "[build] [%d/%d] %s 변환 실패: %s",
                    i + 1, len(flat_blocks), block_name, exc,
                )
                raise
            steps_out.extend(new_steps)

        logger.info("[build] 변환 완료 — %d개 스텝 생성, 임시파일 %d개", len(steps_out), len(ctx.tmp_files))

        return _PostContent(
            title=title,
            steps=steps_out,
            tags=spec.publish.tags,
            visibility=spec.publish.visibility,
            schedule_at=spec.schedule_at,
            align=spec.align,
            tmp_files=ctx.tmp_files,
        )
