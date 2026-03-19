"""
automator/job.py
----------------
PostingJob — platform-agnostic immutable builder + orchestrator.

Builder
-------
    base = PostingJob.for_account(account)

    job = (
        base
        .with_title(TitleOption(template="{region} {subject} {salt}", values={...}))
        .with_body([
            Section(blocks=(
                HeadingBlock(level=2, text="강남 수학 과외 안내"),
                ParagraphBlock(prompt="강남 수학 과외 홍보"),
            ), role="intro"),
            Section(blocks=(
                ImageBlock(path="img.jpg"),
                ParagraphBlock(prompt="후기 형식 마무리"),
                FeaturedImageBlock(path="thumb.jpg"),
            ), role="closing"),
        ])
        .with_publish(PublishOption(mode="immediate", tags=["강남수학과외"]))
    )
    job.run(editor)

with_*() 는 항상 새 인스턴스를 반환한다 — base 는 절대 변하지 않는다.
editor 는 run() 시점에 주입된다.
"""

from __future__ import annotations

import random
import tempfile
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from automator.editor import (
    BlogEditor, PostContent,
    ParagraphStep, ImageStep, ThumbnailStep, PostStep,
)
from automator.title_generator import TitleGenerator, validate_template
from automator.layout import validate_sections, paragraph_block_count, all_blocks
from automator.paragraph_generator import ParagraphGenerator
from automator.seo_prompt import build_prompt
from automator.options import (
    AccountOption,
    TitleOption,
    Section,
    Block, ParagraphBlock, ImageBlock, FeaturedImageBlock,
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
        """설정 오류를 사전에 검출한다."""
        if self._account is None:
            raise ValueError(
                "PostingJob requires an AccountOption. "
                "Use PostingJob.for_account(account)."
            )
        if not self._account.username.strip():
            raise ValueError("AccountOption.username must not be empty")
        if not self._account.password.strip():
            raise ValueError("AccountOption.password must not be empty")

        if self._title is not None and not self._title.fixed_title:
            if self._title.template:
                validate_template(self._title.template)

        validate_sections(self._body)

        if self._publish is not None:
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

        if self._setting is not None:
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
    ) -> PostContent:
        """
        Section 목록에서 PostContent 를 생성한다.

        ParagraphBlock 텍스트 생성 우선순위
        ------------------------------------
        keyword 있음  → build_prompt() 로 SEO 최적화 프롬프트 자동 생성
        keyword 없음  → block.prompt 사용 (비어있으면 stub 텍스트)

        Block → PostStep 변환
        ---------------------
        ParagraphBlock    → ParagraphStep(text, newlines)
        ImageBlock        → ImageStep(path)
        FeaturedImageBlock→ ThumbnailStep(path)
        HeadingBlock      → (현재 에디터 미지원, skip)
        ListBlock         → (현재 에디터 미지원, skip)
        QuoteBlock        → (현재 에디터 미지원, skip)
        DividerBlock      → (현재 에디터 미지원, skip)
        """
        generated_title = TitleGenerator(title).generate()

        flat_blocks    = all_blocks(self._body)
        para_blocks    = [b for b in flat_blocks if isinstance(b, ParagraphBlock)]
        n_paragraphs   = len(para_blocks)
        paragraph_texts: list[str] = []

        if n_paragraphs > 0:
            # keyword 가 있으면 SEO 자동 프롬프트, 없으면 block.prompt 사용
            paragraph_texts = [
                ParagraphGenerator(
                    prompt=build_prompt(b, paragraph_index=i,
                                       total_paragraphs=n_paragraphs)
                ).generate(1)[0]
                for i, b in enumerate(para_blocks)
            ]

        # 빈 body — stub 단락 하나
        if not flat_blocks:
            stub = ParagraphGenerator(prompt="").generate(1)[0]
            return PostContent(
                title=generated_title,
                steps=[ParagraphStep(text=stub, newlines=2)],
                tags=publish.tags,
                schedule_at=self._resolve_schedule(publish),
            )

        # Block → PostStep
        para_idx   = 0
        steps_out: list[PostStep] = []
        for block in flat_blocks:
            if isinstance(block, ParagraphBlock):
                steps_out.append(ParagraphStep(
                    text=paragraph_texts[para_idx],
                    newlines=block.newlines,
                ))
                para_idx += 1
            elif isinstance(block, ImageBlock):
                steps_out.append(ImageStep(path=block.path))
            elif isinstance(block, FeaturedImageBlock):
                steps_out.append(ThumbnailStep(path=block.path))
            # HeadingBlock / ListBlock / QuoteBlock / DividerBlock:
            # 현재 SmartEditorOne 미지원 — 추후 구현

        return PostContent(
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

    def _execute(self, editor: BlogEditor, post: PostContent) -> None:
        """editor 를 구동해 포스트를 발행한다."""
        editor.open()
        editor.write_title(post.title)

        from automator.image_processor import process_image, process_featured, build_filename

        setting            = self._setting
        upload_delay_ms    = (setting.upload_delay_ms if setting else 1500)
        image_upload_count = 0
        rep_index: int | None = None
        tmp_files: list[str] = []

        try:
            for i, step in enumerate(post.steps):
                if i > 0:
                    editor.move_cursor_to_end()

                if isinstance(step, (ImageStep, ThumbnailStep)) and Path(step.path).exists():
                    raw_bytes = Path(step.path).read_bytes()
                    # 블록에서 이미지 처리 설정을 직접 읽는다
                    if isinstance(step, ThumbnailStep):
                        # FeaturedImageBlock 은 flat_blocks 에서 찾는다
                        feat_block = next(
                            (b for b in all_blocks(self._body)
                             if isinstance(b, FeaturedImageBlock) and b.path == step.path),
                            None,
                        )
                        if feat_block is not None:
                            processed = process_featured(raw_bytes, feat_block)
                            fname     = build_filename("featured", image_upload_count + 1,
                                                       feat_block.filename_keyword)
                            tmp = tempfile.NamedTemporaryFile(
                                suffix=".jpg", prefix=fname.replace(".jpg", "_"), delete=False
                            )
                            tmp.write(processed); tmp.close()
                            tmp_files.append(tmp.name)
                            from dataclasses import replace as dc_replace
                            step = dc_replace(step, path=tmp.name)
                    else:
                        img_block = next(
                            (b for b in all_blocks(self._body)
                             if isinstance(b, ImageBlock) and b.path == step.path),
                            None,
                        )
                        if img_block is not None:
                            processed = process_image(raw_bytes, img_block)
                            fname     = build_filename("preview", image_upload_count + 1,
                                                       img_block.filename_keyword)
                            tmp = tempfile.NamedTemporaryFile(
                                suffix=".jpg", prefix=fname.replace(".jpg", "_"), delete=False
                            )
                            tmp.write(processed); tmp.close()
                            tmp_files.append(tmp.name)
                            from dataclasses import replace as dc_replace
                            step = dc_replace(step, path=tmp.name)

                editor.execute(step)

                if isinstance(step, (ImageStep, ThumbnailStep)):
                    if isinstance(step, ThumbnailStep):
                        rep_index = image_upload_count
                    image_upload_count += 1
                    if upload_delay_ms > 0:
                        time.sleep(upload_delay_ms / 1000)

        finally:
            for tmp_path in tmp_files:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass

        if rep_index is not None:
            editor.set_representative_image(rep_index)

        editor.publish(schedule_at=post.schedule_at)
