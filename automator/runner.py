"""
automator/runner.py
--------------------
JobRunner — single entry point for executing a PostingSpec.

    runner = JobRunner(validator, builder)
    runner.run(spec, editor)

All three responsibilities (validate, build content, drive editor) are
delegated to injected collaborators. JobRunner owns only the sequence.
"""

from __future__ import annotations

import logging
from pathlib import Path

from automator.contracts import PostingSpec
from automator.editor import BlogEditor, ImageStep, FeaturedImageStep, _PostContent
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder

logger = logging.getLogger(__name__)


class JobRunner:
    """
    Orchestrator — validate, generate content, execute on editor.

    Args:
        validator: Checks spec before execution.
        builder:   Converts spec into post steps.
    """

    def __init__(
        self,
        validator: SpecValidator,
        builder:   ContentBuilder,
    ) -> None:
        self._validator = validator
        self._builder = builder

    def run(self, spec: PostingSpec, editor: BlogEditor) -> None:
        """
        Execute the full posting workflow.

        Raises:
            ValueError:      Spec validation failure.
            RateLimitError:  Gemini API 429.
            PlaywrightError: Browser/editor failure.
        """
        logger.info("[runner] 스펙 검증 중...")
        self._validator.validate(spec)
        logger.info("[runner] 콘텐츠 빌드 중...")
        post = self._builder.build(spec)
        logger.info("[runner] 콘텐츠 빌드 완료 — %d개 스텝, 제목: %s", len(post.steps), post.title)
        self._execute(editor, post)

    @staticmethod
    def _execute(
        editor: BlogEditor,
        post: _PostContent,
    ) -> None:
        """Drive the editor to publish the post."""
        logger.info("[editor] 에디터 페이지 열기...")
        editor.open()

        if post.align is not None:
            logger.info("[editor] 정렬 설정: %s", post.align)
            editor.set_align(post.align)

        logger.info("[editor] 제목 입력: %s", post.title)
        editor.write_title(post.title)

        total_steps = len(post.steps)
        image_upload_count = 0

        try:
            for i, step in enumerate(post.steps):
                step_name = type(step).__name__
                if i > 0:
                    editor.move_cursor("end")

                logger.info("[editor] [%d/%d] %s 실행 중...", i + 1, total_steps, step_name)
                step.execute(editor)

                wait_ms = getattr(step, "wait_ms", 0)
                if wait_ms > 0:
                    logger.info("[editor] [%d/%d] %s 대기: %.1f초", i + 1, total_steps, step_name, wait_ms / 1000)
                step.wait()

                if isinstance(step, (ImageStep, FeaturedImageStep)):
                    if isinstance(step, FeaturedImageStep) and hasattr(editor, "set_representative_media"):
                        logger.info("[editor] [%d/%d] 대표 이미지 설정 (index=%d)", i + 1, total_steps, image_upload_count)
                        editor.set_representative_media(image_upload_count)
                    image_upload_count += 1

        finally:
            if post.tmp_files:
                logger.info("[runner] 임시 파일 %d개 정리", len(post.tmp_files))
            for path in post.tmp_files:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass

        # Platform-specific: schedule if supported and requested
        if post.schedule_at is not None and hasattr(editor, "schedule"):
            logger.info("[editor] 예약 발행 설정: %s", post.schedule_at.strftime("%Y-%m-%d %H:%M"))
            editor.schedule(post.schedule_at)

        if post.tags:
            logger.info("[editor] 태그 삽입: %s", ", ".join(post.tags))
            editor.insert_tags(post.tags)

        if post.visibility != "public":
            logger.info("[editor] 공개 설정: %s", post.visibility)
            editor.set_visibility(post.visibility)

        logger.info("[editor] 발행 중...")
        editor.publish()
        logger.info("[editor] 발행 완료")
