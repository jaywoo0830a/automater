"""
tests/integration/test_runner.py
----------------------------------
JobRunner.run() — editor call sequence and flow verification.

Replaces: tests/test_job_execution.py
Uses _RecordingEditor to capture primitive calls.
No mock.patch — StubTextGenerator and NoopImageProcessor are injected.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from automator.editor import BlogEditor
from automator.contracts import PostingSpec
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder
from automator.runner import JobRunner
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.options import (
    AccountOption,
    ParagraphBlock, ImageBlock, HeadingBlock, Section,
    PublishOption, KST,
)


_CONTENT_ACTIONS = frozenset({"insert_text", "upload_file"})


class _RecordingEditor(BlogEditor):
    """Captures all primitive calls in order."""

    def __init__(self, dry_run=True):
        super().__init__(dry_run=dry_run)
        self.calls: list[tuple] = []

    def open(self):
        self.calls.append(("open",))

    def write_title(self, title):
        self.calls.append(("title", title))

    def insert_text(self, text, newlines=2):
        self.calls.append(("insert_text", text, newlines))

    def insert_heading(self, text, level=2):
        self.calls.append(("insert_heading", text, level))

    def insert_quote(self, text):
        self.calls.append(("insert_quote", text))

    def insert_divider(self):
        self.calls.append(("insert_divider",))

    def upload_file(self, path):
        self.calls.append(("upload_file", path))

    def insert_link(self, url):
        self.calls.append(("insert_link", url))

    def move_cursor(self, position="end"):
        self.calls.append(("cursor", position))

    def publish(self):
        self.calls.append(("publish",))


def _account():
    return AccountOption(username="id", password="pw")


def _spec(**kw):
    kw.setdefault("account", _account())
    kw.setdefault("title", "T")
    return PostingSpec(**kw)


@pytest.fixture
def runner():
    text_gen = StubTextGenerator()
    img_proc = NoopImageProcessor()
    return JobRunner(SpecValidator(), ContentBuilder(text_gen, img_proc))


@pytest.fixture
def rec():
    return _RecordingEditor()


# ---------------------------------------------------------------------------
# Basic flow
# ---------------------------------------------------------------------------

def test_run_calls_open_title_publish(runner, rec):
    """Minimum run: open -> title -> content -> publish."""
    runner.run(_spec(), rec)
    actions = [c[0] for c in rec.calls]
    assert actions[0] == "open"
    assert actions[1] == "title"
    assert actions[-1] == "publish"


def test_run_with_paragraphs(runner, rec):
    """ParagraphBlocks produce insert_text calls."""
    spec = _spec(body=(Section(blocks=(
        ParagraphBlock(prompt="A"),
        ParagraphBlock(prompt="B"),
    )),))
    runner.run(spec, rec)
    inserts = [c for c in rec.calls if c[0] == "insert_text"]
    assert len(inserts) == 2


def test_run_with_heading(runner, rec):
    """HeadingBlock produces insert_heading call."""
    spec = _spec(body=(Section(blocks=(
        HeadingBlock(level=2, text="Section Title"),
    )),))
    runner.run(spec, rec)
    inserts = [c for c in rec.calls if c[0] == "insert_heading"]
    assert len(inserts) == 1
    assert inserts[0][1] == "Section Title"
    assert inserts[0][2] == 2


def test_cursor_between_steps(runner, rec):
    """cursor("end") is called between content steps."""
    spec = _spec(body=(Section(blocks=(
        ParagraphBlock(prompt="A"),
        ParagraphBlock(prompt="B"),
    )),))
    runner.run(spec, rec)
    cursors = [c for c in rec.calls if c[0] == "cursor"]
    assert len(cursors) >= 1


def test_publish_schedule_at(runner):
    """Fixed schedule calls editor.schedule() before publish()."""

    class _SchedulingEditor(_RecordingEditor):
        def schedule(self, at):
            self.calls.append(("schedule", at))

    editor = _SchedulingEditor()
    future = datetime.now(tz=KST) + timedelta(hours=2)
    spec = _spec(publish=PublishOption(mode="scheduled", at=future))
    runner.run(spec, editor)

    actions = [c[0] for c in editor.calls]
    assert "schedule" in actions
    assert actions.index("schedule") < actions.index("publish")

    sched_call = [c for c in editor.calls if c[0] == "schedule"][0]
    assert sched_call[1] == future


def test_empty_body_gets_stub_paragraph(runner, rec):
    """Empty body generates a stub paragraph."""
    runner.run(_spec(body=()), rec)
    inserts = [c for c in rec.calls if c[0] == "insert_text"]
    assert len(inserts) == 1
