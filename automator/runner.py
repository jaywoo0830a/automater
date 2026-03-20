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

import time
from pathlib import Path

from automator.contracts import PostingSpec
from automator.editor import BlogEditor, _PostContent
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
        self._execute(editor, post, spec)

    @staticmethod
    def _execute(
        editor: BlogEditor,
        post: _PostContent,
        spec: PostingSpec,
    ) -> None:
        """Drive the editor to publish the post."""
        editor.open()
        editor.write_title(post.title)

        upload_delay_ms = spec.setting.upload_delay_ms
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
            for path in post.tmp_files:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass

        if rep_index is not None:
            editor.set_representative_media(rep_index)

        editor.publish(schedule_at=post.schedule_at)
