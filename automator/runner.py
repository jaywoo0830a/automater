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

from pathlib import Path

from automator.contracts import PostingSpec
from automator.editor import BlogEditor, ImageStep, FeaturedImageStep, _PostContent
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder


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
        self._validator.validate(spec)
        post = self._builder.build(spec)
        self._execute(editor, post)

    @staticmethod
    def _execute(
        editor: BlogEditor,
        post: _PostContent,
    ) -> None:
        """Drive the editor to publish the post."""
        editor.open()

        if post.align is not None:
            editor.set_align(post.align)

        editor.write_title(post.title)

        image_upload_count = 0

        try:
            for i, step in enumerate(post.steps):
                if i > 0:
                    editor.move_cursor("end")

                step.execute(editor)
                step.wait()

                if isinstance(step, (ImageStep, FeaturedImageStep)):
                    if isinstance(step, FeaturedImageStep) and hasattr(editor, "set_representative_media"):
                        editor.set_representative_media(image_upload_count)
                    image_upload_count += 1

        finally:
            for path in post.tmp_files:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass

        # Platform-specific: schedule if supported and requested
        if post.schedule_at is not None and hasattr(editor, "schedule"):
            editor.schedule(post.schedule_at)

        if post.tags:
            editor.insert_tags(post.tags)

        editor.publish()
