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
            ImageBlock(path="img.jpg"),
            TextBlock(prompt="강남 수학 과외 홍보"),
            FeaturedBlock(path="thumb.jpg"),
            TextBlock(prompt="후기 형식 마무리"),
        ])
        .with_seo(SEOOption(keyword="강남 수학 과외", tone="review_style"))
        .with_media(MediaOption(pixel_jitter=True, exif_gps_lat=37.49,
                                featured_overlay_text="강남 수학"))
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
from automator.layout import validate_blocks, text_block_count
from automator.paragraph_generator import ParagraphGenerator
from automator.seo_prompt import to_prompt
from automator.options import (
    AccountOption,
    TitleOption,
    Block, TextBlock, ImageBlock, FeaturedBlock,
    MediaOption,
    PublishOption,
    SEOOption,
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

    _account: AccountOption   | None = field(default=None, repr=False)
    _title:   TitleOption     | None = field(default=None, repr=False)
    _body:    list[Block]            = field(default_factory=list, repr=False)
    _seo:     SEOOption       | None = field(default=None, repr=False)
    _media:   MediaOption     | None = field(default=None, repr=False)
    _publish: PublishOption   | None = field(default=None, repr=False)
    _setting: RunSetting      | None = field(default=None, repr=False)

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

    def with_body(self, blocks: list[Block]) -> "PostingJob":
        """
        포스트 본문을 Block 목록으로 설정한 새 인스턴스를 반환한다.

        Block 의 순서가 곧 레이아웃이다.
          TextBlock     → 단락 텍스트
          ImageBlock    → 본문 이미지
          FeaturedBlock → 대표(썸네일) 이미지  (최대 1개)
        """
        return replace(self, _body=list(blocks))

    def with_seo(self, seo: SEOOption) -> "PostingJob":
        """
        SEO 옵션을 설정한 새 인스턴스를 반환한다.

        설정 시 TextBlock.prompt 보다 우선하며,
        단락 위치(첫/중간/마지막)마다 다른 Gemini 프롬프트가 생성된다.
        """
        return replace(self, _seo=seo)

    def with_media(self, media: MediaOption) -> "PostingJob":
        """
        이미지 변환 파이프라인을 설정한 새 인스턴스를 반환한다.

        파일 경로를 알지 못한다. 모든 이미지 블록에 동일 규칙이 적용된다.
        """
        return replace(self, _media=media)

    def with_publish(self, publish: PublishOption) -> "PostingJob":
        """
        발행 설정(일정·태그·공개범위)을 지정한 새 인스턴스를 반환한다.
        """
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
        Factory 레이어가 포착·로깅·계속 진행할 책임을 가진다.

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
        """
        설정 오류를 사전에 검출한다.
        run() 이 브라우저를 열기 전에 호출된다.
        """
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

        validate_blocks(self._body)

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
        Block 목록에서 PostContent 를 생성한다.

        TextBlock 단락 생성 우선순위
        ----------------------------
        1. SEOOption 있음  → 위치(첫/중간/마지막)별 개별 Gemini 프롬프트
        2. TextBlock.prompt 있음 → 해당 프롬프트로 Gemini 호출
        3. 둘 다 없음      → ParagraphGenerator(prompt="") → stub 텍스트

        Block → PostStep 변환
        ---------------------
        TextBlock     → ParagraphStep(text, newlines)
        ImageBlock    → ImageStep(path)
        FeaturedBlock → ThumbnailStep(path)
        """
        generated_title = TitleGenerator(title).generate()

        # 단락 텍스트 미리 생성
        text_blocks    = [b for b in self._body if isinstance(b, TextBlock)]
        n_paragraphs   = len(text_blocks)
        seo            = self._seo
        paragraph_texts: list[str] = []

        if n_paragraphs > 0:
            if seo is not None:
                paragraph_texts = [
                    ParagraphGenerator(
                        prompt=to_prompt(seo, paragraph_index=i,
                                         total_paragraphs=n_paragraphs)
                    ).generate(1)[0]
                    for i in range(n_paragraphs)
                ]
            else:
                # TextBlock 마다 개별 prompt 사용
                if all(b.prompt for b in text_blocks):
                    # 각 블록이 고유 프롬프트를 가진 경우
                    paragraph_texts = [
                        ParagraphGenerator(prompt=b.prompt).generate(1)[0]
                        for b in text_blocks
                    ]
                else:
                    # 첫 번째 블록의 prompt 를 공유 (하위 호환)
                    shared_prompt  = text_blocks[0].prompt if text_blocks else ""
                    paragraph_texts = ParagraphGenerator(
                        prompt=shared_prompt
                    ).generate(n_paragraphs)

        # 빈 body — stub 단락 하나
        if not self._body:
            stub = ParagraphGenerator(prompt="").generate(1)[0]
            steps: list[PostStep] = [ParagraphStep(text=stub, newlines=2)]
            return PostContent(
                title=generated_title,
                steps=steps,
                tags=publish.tags,
                schedule_at=self._resolve_schedule(publish),
            )

        # Block → PostStep
        text_idx    = 0
        steps_out: list[PostStep] = []
        for block in self._body:
            if isinstance(block, TextBlock):
                steps_out.append(ParagraphStep(
                    text=paragraph_texts[text_idx],
                    newlines=block.newlines,
                ))
                text_idx += 1
            elif isinstance(block, ImageBlock):
                steps_out.append(ImageStep(path=block.path))
            elif isinstance(block, FeaturedBlock):
                steps_out.append(ThumbnailStep(path=block.path))

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
        """
        editor 를 구동해 포스트를 발행한다.

        MediaOption 설정 시:
          ImageStep    → process_preview()  적용
          ThumbnailStep → process_featured() 적용 (오버레이 포함)
          변환된 bytes 는 임시 파일에 저장 → finally 에서 정리.
        """
        editor.open()
        editor.write_title(post.title)

        media     = self._media
        processor = None
        if media is not None:
            from automator.image_processor import ImageProcessor
            processor = ImageProcessor(media)

        image_upload_count = 0
        rep_index: int | None = None
        tmp_files: list[str] = []

        try:
            for i, step in enumerate(post.steps):
                if i > 0:
                    editor.move_cursor_to_end()

                if processor is not None and isinstance(step, (ImageStep, ThumbnailStep)):
                    src = Path(step.path).read_bytes()
                    processed = (
                        processor.process_featured(src, keyword=media.exif_description)
                        if isinstance(step, ThumbnailStep)
                        else processor.process_preview(src, keyword=media.exif_description)
                    )
                    role  = "featured" if isinstance(step, ThumbnailStep) else "preview"
                    fname = processor.build_filename(role, image_upload_count + 1)
                    tmp   = tempfile.NamedTemporaryFile(
                        suffix=".jpg",
                        prefix=fname.replace(".jpg", "_"),
                        delete=False,
                    )
                    tmp.write(processed)
                    tmp.close()
                    tmp_files.append(tmp.name)
                    from dataclasses import replace as dc_replace
                    step = dc_replace(step, path=tmp.name)

                editor.execute(step)

                if isinstance(step, (ImageStep, ThumbnailStep)):
                    if isinstance(step, ThumbnailStep):
                        rep_index = image_upload_count
                    image_upload_count += 1
                    if media is not None and media.upload_delay_ms > 0:
                        time.sleep(media.upload_delay_ms / 1000)

        finally:
            for tmp_path in tmp_files:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass

        if rep_index is not None:
            editor.set_representative_image(rep_index)

        editor.publish(schedule_at=post.schedule_at)
