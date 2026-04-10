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
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from automator.contracts import PostingSpec
from automator.editor import BlogEditor, ImageStep, FeaturedImageStep, _PostContent
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder

logger = logging.getLogger(__name__)

# 에디터 열기 재시도 설정
_OPEN_MAX_RETRIES = 3
_OPEN_RETRY_DELAY = 5  # seconds


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
        # 에디터 열기 — 네트워크/세션 문제에 대비하여 재시도
        for attempt in range(1, _OPEN_MAX_RETRIES + 1):
            try:
                logger.info("[editor] 에디터 페이지 열기...")
                editor.open()
                break
            except (PlaywrightTimeout, Exception) as exc:
                if attempt < _OPEN_MAX_RETRIES:
                    logger.warning(
                        "[editor] 에디터 열기 실패 (시도 %d/%d): %s — %d초 후 재시도",
                        attempt, _OPEN_MAX_RETRIES, exc, _OPEN_RETRY_DELAY,
                    )
                    time.sleep(_OPEN_RETRY_DELAY)
                else:
                    logger.error("[editor] 에디터 열기 최종 실패: %s", exc)
                    raise

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

                # 각 step 직전에 방해 오버레이 제거 (초안 복구, 도움말, 미디어 라이브러리)
                # 도중에 뜨는 팝업이 도미노 실패를 일으키는 걸 방지한다.
                if editor.dismiss_overlays():
                    logger.info("[editor] [%d/%d] 오버레이 감지 및 제거", i + 1, total_steps)

                logger.info("[editor] [%d/%d] %s 실행 중...", i + 1, total_steps, step_name)
                step.execute(editor)

                wait_ms = getattr(step, "wait_ms", 0)
                if wait_ms > 0:
                    logger.info("[editor] [%d/%d] %s 대기: %.1f초", i + 1, total_steps, step_name, wait_ms / 1000)
                step.wait()

                if isinstance(step, (ImageStep, FeaturedImageStep)):
                    if isinstance(step, FeaturedImageStep) and hasattr(editor, "set_representative_media"):
                        # 대표이미지 설정 직전에도 오버레이 probe
                        editor.dismiss_overlays()
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
            editor.dismiss_overlays()
            logger.info("[editor] 예약 발행 설정: %s", post.schedule_at.strftime("%Y-%m-%d %H:%M"))
            editor.schedule(post.schedule_at)

        if post.tags:
            editor.dismiss_overlays()
            logger.info("[editor] 태그 삽입: %s", ", ".join(post.tags))
            editor.insert_tags(post.tags)

        if post.visibility != "public":
            editor.dismiss_overlays()
            logger.info("[editor] 공개 설정: %s", post.visibility)
            editor.set_visibility(post.visibility)

        editor.dismiss_overlays()
        logger.info("[editor] 발행 중...")
        editor.publish()
        logger.info("[editor] 발행 완료")
