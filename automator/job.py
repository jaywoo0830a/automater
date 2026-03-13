"""
automator/job.py
----------------
NaverBlogJob — immutable builder + orchestrator for a blog post publishing run.

This module has zero knowledge of DOM, CSS, or Playwright. It expresses
the business flow purely in terms of the BlogEditor interface and the
option value objects.

Builder pattern
---------------
    base = NaverBlogJob.for_account(account).with_setting(setting)

    job_a = base.with_title(title_a).with_content(content_a).with_meta(meta_a)
    job_b = base.with_title(title_b).with_content(content_b).with_meta(meta_b)

    job_a.run(editor)
    job_b.run(editor)

Each .with_*() returns a NEW instance so the base is never mutated.
The editor is injected at run() time because it requires a live Playwright Page.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from automator.editor import BlogEditor, PostContent
from automator.title_generator import TitleGenerator, validate_template
from automator.layout import validate_layout, paragraph_count, parse_alias
from automator.options import (
    AccountOption,
    TitleOption,
    ContentOption,
    MetaOption,
    RunSetting,
)


@dataclass
class NaverBlogJob:
    """
    Immutable builder and orchestrator for a single Naver Blog post.

    Entry point:

        job = (
            NaverBlogJob
            .for_account(AccountOption(naver_id="id", naver_pw="pw", blog_id="blog"))
            .with_title(TitleOption(subjects=["국어", "수학"]))
            .with_content(ContentOption(paragraph_count=5))
            .with_meta(MetaOption(min_tags=10, max_tags=15))
            .with_setting(RunSetting(post_interval=30))
        )

        success = job.run(editor)   # editor = SmartEditorOne(page, account.write_url)
    """

    _account: AccountOption | None = field(default=None, repr=False)
    _title:   TitleOption   | None = field(default=None, repr=False)
    _content: ContentOption | None = field(default=None, repr=False)
    _meta:    MetaOption    | None = field(default=None, repr=False)
    _setting: RunSetting    | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    @classmethod
    def for_account(cls, account: AccountOption) -> "NaverBlogJob":
        """Start building a job for the given account."""
        return cls(_account=account)

    def with_title(self, title: TitleOption) -> "NaverBlogJob":
        """Return a new job with the given title option."""
        return replace(self, _title=title)

    def with_content(self, content: ContentOption) -> "NaverBlogJob":
        """Return a new job with the given content option."""
        return replace(self, _content=content)

    def with_meta(self, meta: MetaOption) -> "NaverBlogJob":
        """Return a new job with the given meta option."""
        return replace(self, _meta=meta)

    def with_setting(self, setting: RunSetting) -> "NaverBlogJob":
        """Return a new job with the given run setting."""
        return replace(self, _setting=setting)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, editor: BlogEditor) -> bool:
        """
        Generate content from options and publish via the editor.

        Raises:
            ValueError: If required options are missing or invalid.
                        Raised before the editor is touched.

        Returns:
            True  — published successfully.
            False — a browser/editor error occurred; details on stderr.
        """
        self.validate()  # programming errors — let them propagate

        title   = self._title   or TitleOption()
        content = self._content or ContentOption()
        meta    = self._meta    or MetaOption()

        post = self._generate_content(title, content, meta)

        try:
            self._execute(editor, post)
            return True
        except Exception as exc:
            print(f"[NaverBlogJob] FAILED: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Raise ValueError for missing or invalid configuration.

        Called by run() before the browser is touched.
        Can also be called directly to pre-check a job.
        """
        if self._account is None:
            raise ValueError(
                "NaverBlogJob requires an AccountOption. "
                "Use NaverBlogJob.for_account(account)."
            )
        if not self._account.naver_id.strip():
            raise ValueError("AccountOption.naver_id must not be empty")
        if not self._account.naver_pw.strip():
            raise ValueError("AccountOption.naver_pw must not be empty")
        if not self._account.blog_id.strip():
            raise ValueError("AccountOption.blog_id must not be empty")
        if self._account.post_count < 1:
            raise ValueError("AccountOption.post_count must be >= 1")

        if self._title is not None:
            validate_template(self._title.template)

        if self._content is not None:
            validate_layout(self._content)

        if self._meta is not None:
            if self._meta.min_tags > self._meta.max_tags:
                raise ValueError("MetaOption.min_tags must be <= max_tags")
            if not (0 <= self._meta.backlink_ratio <= 100):
                raise ValueError("MetaOption.backlink_ratio must be 0–100")
            if not (0 <= self._meta.internal_link_ratio <= 100):
                raise ValueError("MetaOption.internal_link_ratio must be 0–100")

        if self._setting is not None:
            if self._setting.post_interval < 0:
                raise ValueError("RunSetting.post_interval must be >= 0")
            if self._setting.max_daily_posts < 1:
                raise ValueError("RunSetting.max_daily_posts must be >= 1")

    # ------------------------------------------------------------------
    # Content generation (stub — replaced by AI generator later)
    # ------------------------------------------------------------------

    def _generate_content(
        self,
        title:   TitleOption,
        content: ContentOption,
        meta:    MetaOption,
    ) -> PostContent:
        """
        Produce a PostContent from options.

        Layout processing
        -----------------
        Iterates content.layout in order:
          - "Image N"     → preview_images[N-1] added to upload queue
          - "Thumbnail N" → thumbnail_images[N-1] added to upload queue,
                            marked as representative image
          - "Paragraph N" → body paragraphs are generated (stub)

        Paragraph count is derived from layout automatically.
        The PostContent contract is stable — the editor layer never changes
        regardless of how content is generated here.
        """
        generated_title = TitleGenerator(title).generate()

        # Build ordered image list and locate representative index from layout
        images:    list[str]  = []
        rep_index: int | None = None

        n_paragraphs = paragraph_count(content.layout)
        # Stub: generate placeholder paragraphs (replaced by AI pipeline later)
        paragraphs = [f"(단락 {i} 생성 필요)" for i in range(1, n_paragraphs + 1)]

        for alias in content.layout:
            kind, n = parse_alias(alias)
            if kind == "image":
                images.append(content.preview_images[n - 1])
            elif kind == "thumbnail":
                images.append(content.thumbnail_images[n - 1])
                rep_index = len(images) - 1

        body = "\n\n".join(paragraphs) if paragraphs else "(본문 생성 필요)"

        return PostContent(
            title=generated_title,
            body=body,
            images=images,
            representative_image=rep_index,
            tags=[],
        )

    # ------------------------------------------------------------------
    # Editor execution
    # ------------------------------------------------------------------

    def _execute(self, editor: BlogEditor, post: PostContent) -> None:
        """Drive the editor through the full publish sequence."""
        editor.open()
        editor.write_title(post.title)
        editor.write_body(post.body)
        self._upload_images(editor, post)
        editor.publish()

    def _upload_images(self, editor: BlogEditor, post: PostContent) -> None:
        """Upload all images, moving cursor to end between each."""
        for i, path in enumerate(post.images):
            if i > 0:
                editor.move_cursor_to_end()
            editor.upload_image(path)

        if post.representative_image is not None:
            editor.set_representative_image(post.representative_image)
