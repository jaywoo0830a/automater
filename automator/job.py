"""
automator/job.py
----------------
PostingJob — immutable builder + orchestrator.

Public interface
----------------
    PostingJob.for_account(account)     -> PostingJob
    PostingJob.with_title(title)        -> PostingJob
    PostingJob.with_body(sections)      -> PostingJob
    PostingJob.with_publish(publish)    -> PostingJob
    PostingJob.with_setting(setting)    -> PostingJob
    PostingJob.run(editor)              -> None
    PostingJob.validate()               -> None

Internal flow (run)
-------------------
    1. validate()
    2. _generate_content() — BlockHandler.to_steps() per block
    3. _execute()          — step.execute(editor) per step
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from automator.editor import (
    BlogEditor, _PostContent,
    ParagraphStep,
)
from automator.block_handlers import ContentContext, get_handler
from automator.title_generator import generate_title, validate_template
from automator.layout import validate_sections, paragraph_block_count, all_blocks
from automator.paragraph_generator import generate_paragraphs
from automator.options import (
    AccountOption,
    TitleOption,
    Section,
    PublishOption,
    RunSetting,
    KST,
)


@dataclass
class PostingJob:
    """
    플랫폼 독립적인 포스팅 잡 빌더 + 오케스트레이터.

    최소 사용:
        job = PostingJob.for_account(account).with_title(TitleOption(fixed_title="제목"))
        job.run(editor)
    """

    _account: AccountOption   | None = field(default=None,        repr=False)
    _title:   TitleOption     | None = field(default=None,        repr=False)
    _body:    list[Section]          = field(default_factory=list, repr=False)
    _publish: PublishOption   | None = field(default=None,        repr=False)
    _setting: RunSetting      | None = field(default=None,        repr=False)

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    @classmethod
    def for_account(cls, account: AccountOption) -> "PostingJob":
        """계정 정보로 잡 빌드를 시작한다."""
        return cls(_account=account)

    def with_title(self, title: TitleOption) -> "PostingJob":
        """제목 옵션을 설정한 새 인스턴스를 반환한다."""
        return replace(self, _title=title)

    def with_body(self, sections: list[Section]) -> "PostingJob":
        """
        포스트 본문을 Section 목록으로 설정한 새 인스턴스를 반환한다.

        Section 안의 Block 순서가 곧 레이아웃이다.
          ParagraphBlock    → 텍스트 단락
          ImageBlock        → 본문 이미지
          FeaturedImageBlock→ 대표(썸네일) 이미지  (전체 섹션에서 최대 1개)
          HeadingBlock      → 제목
          ListBlock         → 목록
          QuoteBlock        → 인용문
          DividerBlock      → 구분선
        """
        return replace(self, _body=list(sections))

    def with_publish(self, publish: PublishOption) -> "PostingJob":
        """발행 설정(일정·태그·공개범위)을 지정한 새 인스턴스를 반환한다."""
        return replace(self, _publish=publish)

    def with_setting(self, setting: RunSetting) -> "PostingJob":
        """실행 엔진 설정을 지정한 새 인스턴스를 반환한다."""
        return replace(self, _setting=setting)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, editor: BlogEditor) -> None:
        """
        콘텐츠를 생성하고 editor 를 통해 발행한다.

        모든 예외는 그대로 전파된다.

        Raises:
            ValueError:      필수 옵션 누락 또는 유효하지 않은 값.
            RateLimitError:  Gemini API 429.
            PlaywrightError: 브라우저/에디터 조작 실패.
        """
        self.validate()

        title   = self._title   or TitleOption()
        publish = self._publish or PublishOption()

        post = self._generate_content(title, publish)
        self._execute(editor, post)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Detect configuration errors before execution."""
        self._validate_account()
        self._validate_title()
        validate_sections(self._body)
        self._validate_publish()
        self._validate_setting()

    def _validate_account(self) -> None:
        if self._account is None:
            raise ValueError(
                "PostingJob requires an AccountOption. "
                "Use PostingJob.for_account(account)."
            )
        if not self._account.username.strip():
            raise ValueError("AccountOption.username must not be empty")
        if not self._account.password.strip():
            raise ValueError("AccountOption.password must not be empty")

    def _validate_title(self) -> None:
        if self._title is not None and not self._title.fixed_title:
            if self._title.template:
                validate_template(self._title.template)

    def _validate_publish(self) -> None:
        if self._publish is None:
            return

        pub = self._publish
        if pub.min_tags > pub.max_tags:
            raise ValueError("PublishOption.min_tags must be <= max_tags")
        if not (0 <= pub.backlink_ratio <= 100):
            raise ValueError("PublishOption.backlink_ratio must be 0–100")
        if not (0 <= pub.internal_link_ratio <= 100):
            raise ValueError("PublishOption.internal_link_ratio must be 0–100")

        mode = pub.mode
        if mode != "immediate":
            if pub.at is None:
                raise ValueError(
                    f"PublishOption.at 은 mode='{mode}'일 때 필수입니다."
                )
            if pub.at.tzinfo is None:
                raise ValueError(
                    "PublishOption.at 은 timezone-aware datetime 이어야 합니다. "
                    "예: datetime(2025, 6, 1, 9, 0, tzinfo=KST)"
                )
            now      = datetime.now(tz=KST)
            earliest = (
                pub.at - timedelta(minutes=pub.jitter_minutes)
                if mode == "random_window"
                else pub.at
            )
            if earliest <= now:
                raise ValueError(
                    "PublishOption.at 은 현재 시각보다 미래여야 합니다. "
                    f"(earliest={earliest.isoformat()}, now={now.isoformat()})"
                )
        if mode == "random_window" and pub.jitter_minutes <= 0:
            raise ValueError(
                f"PublishOption.jitter_minutes 은 양수여야 합니다. "
                f"(got {pub.jitter_minutes})"
            )

    def _validate_setting(self) -> None:
        if self._setting is None:
            return
        if self._setting.post_interval < 0:
            raise ValueError("RunSetting.post_interval must be >= 0")
        if self._setting.max_daily_posts < 1:
            raise ValueError("RunSetting.max_daily_posts must be >= 1")

    # ------------------------------------------------------------------
    # Content generation
    # ------------------------------------------------------------------

    def _generate_content(
        self,
        title:   TitleOption,
        publish: PublishOption,
    ) -> _PostContent:
        """
        Convert Section list into _PostContent using BlockHandlers.

        Each Block is dispatched to its registered handler via get_handler().
        No isinstance branching — adding a new Block type only requires
        a new BlockHandler + registry entry.
        """
        generated_title = generate_title(title)

        flat_blocks = all_blocks(self._body)
        para_count  = paragraph_block_count(self._body)

        if not flat_blocks:
            stub = generate_paragraphs("", 1)[0]
            return _PostContent(
                title=generated_title,
                steps=[ParagraphStep(text=stub, newlines=2)],
                tags=publish.tags,
                schedule_at=self._resolve_schedule(publish),
            )

        ctx = ContentContext(
            paragraph_index=0,
            total_paragraphs=para_count,
        )

        steps_out: list[PostStep] = []
        for block in flat_blocks:
            handler = get_handler(block)
            steps_out.extend(handler.to_steps(block, ctx))

        self._tmp_files = ctx.tmp_files

        return _PostContent(
            title=generated_title,
            steps=steps_out,
            tags=publish.tags,
            schedule_at=self._resolve_schedule(publish),
        )

    # ------------------------------------------------------------------
    # Schedule resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_schedule(publish: PublishOption) -> datetime | None:
        if publish.mode == "immediate":
            return None
        if publish.mode == "fixed":
            return publish.at
        jitter = publish.jitter_minutes * 60
        return publish.at + timedelta(seconds=random.uniform(-jitter, jitter))

    # ------------------------------------------------------------------
    # Editor execution
    # ------------------------------------------------------------------

    def _execute(self, editor: BlogEditor, post: _PostContent) -> None:
        """
        Drive the editor to publish the post.

        Each step executes itself via step.execute(editor) — no isinstance.
        Orchestration properties (needs_upload_delay, marks_representative)
        are checked polymorphically.
        """
        editor.open()
        editor.write_title(post.title)

        upload_delay_ms = self._setting.upload_delay_ms if self._setting else 1500
        image_upload_count = 0
        rep_index: int | None = None

        try:
            for i, step in enumerate(post.steps):
                if i > 0:
                    editor.move_cursor("end")

                step.execute(editor)

                if step.marks_representative:
                    rep_index = image_upload_count

                if step.needs_upload_delay:
                    image_upload_count += 1
                    if upload_delay_ms > 0:
                        time.sleep(upload_delay_ms / 1000)

        finally:
            for path in getattr(self, '_tmp_files', []):
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass

        if rep_index is not None:
            editor.set_representative_image(rep_index)

        editor.publish(schedule_at=post.schedule_at)
