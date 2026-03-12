"""
automator/job.py
----------------
NaverBlogJob — orchestrates a single blog post publishing run.

This module has zero knowledge of DOM, CSS, or Playwright. It expresses
the business flow purely in terms of the BlogEditor interface. If the
editor implementation changes, this file stays the same.

Usage:
    from playwright.sync_api import sync_playwright
    from automator.job import NaverBlogJob
    from automator.editor import PostContent
    from automator.smart_editor import SmartEditorOne
    from automator.config import settings

    content = PostContent(
        title  = "제목",
        body   = "본문",
        images = ["photo.jpg"],
        representative_image = 0,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx     = browser.new_context()
        page    = ctx.new_page()
        editor  = SmartEditorOne(page, settings.write_url)
        job     = NaverBlogJob(editor)
        success = job.run(content)
"""

from __future__ import annotations

import sys

from automator.editor import BlogEditor, PostContent


class NaverBlogJob:
    """
    Orchestrates a complete blog post publishing run.

    Responsibilities:
      - Validate content before starting the browser
      - Drive the editor through the publish sequence
      - Return a boolean result so callers can act on success/failure
        without catching exceptions

    This class never imports Playwright or any browser module directly.
    All browser interaction is delegated to the injected BlogEditor.

    Args:
        editor: A ready-to-use BlogEditor implementation.
    """

    def __init__(self, editor: BlogEditor) -> None:
        self._editor = editor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, content: PostContent) -> bool:
        """
        Execute the full publish sequence for ``content``.

        Sequence:
          1. Validate content (raises ValueError before touching the browser)
          2. Open the editor
          3. Write title
          4. Write body
          5. Upload images (move cursor to end between each)
          6. Set representative image (if requested)
          7. Publish

        Returns:
            True  — post was published successfully.
            False — an error occurred; details printed to stderr.
        """
        self.validate(content)  # programming error — let it propagate

        try:
            self._editor.open()
            self._editor.write_title(content.title)
            self._editor.write_body(content.body)
            self._upload_images(content)
            self._editor.publish()
            return True
        except Exception as exc:
            print(f"[NaverBlogJob] FAILED: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def validate(self, content: PostContent) -> None:
        """
        Raise ValueError for obviously invalid content.

        Checked before the browser is opened so the user gets immediate
        feedback without waiting for a page load.
        """
        if not content.title or not content.title.strip():
            raise ValueError("PostContent.title must not be empty")
        if not content.body or not content.body.strip():
            raise ValueError("PostContent.body must not be empty")
        if content.representative_image is not None:
            if not content.images:
                raise ValueError(
                    "PostContent.representative_image is set "
                    "but no images were provided"
                )
            if content.representative_image >= len(content.images):
                raise ValueError(
                    f"PostContent.representative_image={content.representative_image} "
                    f"is out of range (only {len(content.images)} image(s) provided)"
                )

    def _upload_images(self, content: PostContent) -> None:
        """
        Upload all images, moving the cursor to the end between each.

        After all uploads, sets the representative image if requested.
        """
        for i, path in enumerate(content.images):
            if i > 0:
                # Move cursor so the next image appends as a new block
                self._editor.move_cursor_to_end()
            self._editor.upload_image(path)

        if content.representative_image is not None:
            self._editor.set_representative_image(content.representative_image)
