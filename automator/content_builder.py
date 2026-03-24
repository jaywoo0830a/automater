"""
automator/content_builder.py
------------------------------
ContentBuilder — converts a PostingSpec into executable PostSteps.

Depends on TextGenerator and ImageProcessor ABCs (ports), never on
concrete implementations. Concrete instances are injected in __init__.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from automator.contracts import PostingSpec
from automator.editor import PostStep, ParagraphStep, _PostContent
from automator.block_handlers import ContentContext, get_handler
from automator.layout import all_blocks, paragraph_block_count
from automator.ports import TextGenerator, ImageProcessor
from automator.title_generator import generate_title
from automator.options import PublishOption


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
        title = generate_title(spec.title)
        flat_blocks = all_blocks(list(spec.body))
        para_count = paragraph_block_count(list(spec.body))

        if not flat_blocks:
            stub = self._text_gen.generate("", 1)[0]
            return _PostContent(
                title=title,
                steps=[ParagraphStep(text=stub, newlines=2)],
                tags=spec.publish.tags,
                schedule_at=self._resolve_schedule(spec.publish),
            )

        ctx = ContentContext(
            paragraph_index=0,
            total_paragraphs=para_count,
            text_gen=self._text_gen,
            img_proc=self._img_proc,
        )

        steps_out: list[PostStep] = []
        for block in flat_blocks:
            handler = get_handler(block)
            steps_out.extend(handler.to_steps(block, ctx))

        return _PostContent(
            title=title,
            steps=steps_out,
            tags=spec.publish.tags,
            schedule_at=self._resolve_schedule(spec.publish),
            tmp_files=ctx.tmp_files,
        )

    @staticmethod
    def _resolve_schedule(publish: PublishOption) -> datetime | None:
        """Compute the actual publish datetime from publish options."""
        if publish.mode == "immediate":
            return None
        return publish.at
