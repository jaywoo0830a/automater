"""
tests/test_job_execution.py
----------------------------
PostingJob.run() — editor call sequence and flow verification.

_RecordingEditor captures primitive calls (insert_text, upload_file).
Each PostStep calls the primitive directly via step.execute(editor).
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from automator.editor import BlogEditor
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption,
    ParagraphBlock, ImageBlock, FeaturedImageBlock, HeadingBlock, Section,
    PublishOption, KST,
)


_CONTENT_ACTIONS = frozenset({
    "insert_text", "upload_file",
})


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


class _RecordingEditor(BlogEditor):
    """Records all primitive calls in order."""

    def __init__(self):
        self.actions: list[tuple] = []

    def _rec(self, name, *args):
        self.actions.append((name, *args))

    def open(self)                             -> None: self._rec("open")
    def write_title(self, t)                   -> None: self._rec("write_title", t)
    def insert_text(self, text, nl=2)          -> None: self._rec("insert_text", text, nl)
    def upload_file(self, path)                -> None: self._rec("upload_file", path)
    def set_representative_image(self, i)      -> None: self._rec("set_rep", i)
    def move_cursor(self, position="end")      -> None: self._rec("cursor", position)
    def publish(self, schedule_at=None)        -> None: self._rec("publish", schedule_at)

    def content_actions(self) -> list[tuple]:
        """Return only content-producing actions (write/upload)."""
        return [a for a in self.actions if a[0] in _CONTENT_ACTIONS]


@pytest.fixture
def editor():
    return _RecordingEditor()


def _base_job():
    return PostingJob.for_account(_account())


# ---------------------------------------------------------------------------
# Call ordering
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_open_is_called_before_write_title(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    names = [a[0] for a in editor.actions]
    assert names.index("open") < names.index("write_title")


@pytest.mark.unit
def test_write_title_is_called_before_any_content(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(),))]).run(editor)
    names = [a[0] for a in editor.actions]
    first_content = next(i for i, n in enumerate(names) if n in _CONTENT_ACTIONS)
    assert names.index("write_title") < first_content


@pytest.mark.unit
def test_publish_is_always_the_last_action(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    assert editor.actions[-1][0] == "publish"


# ---------------------------------------------------------------------------
# Empty body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_empty_body__generates_one_stub_paragraph(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    content = editor.content_actions()
    assert len(content) == 1
    assert content[0][0] == "insert_text"


@pytest.mark.unit
def test_empty_body__still_calls_publish(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    assert any(a[0] == "publish" for a in editor.actions)


# ---------------------------------------------------------------------------
# Block -> primitive call mapping and order
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_blocks_are_executed_in_declared_order(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([
                   Section(blocks=(
                       ImageBlock(path="img.jpg"),
                       ParagraphBlock(),
                       FeaturedImageBlock(path="thumb.jpg"),
                   )),
               ]).run(editor)

    content = editor.content_actions()
    primitives = [a[0] for a in content]
    assert primitives == ["upload_file", "insert_text", "upload_file"]


@pytest.mark.unit
def test_paragraph_block__calls_insert_text(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(newlines=3),))]).run(editor)
    content = editor.content_actions()
    assert content[0][0] == "insert_text"


@pytest.mark.unit
def test_image_block__calls_upload_file(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ImageBlock(path="img.jpg"),))]).run(editor)
    content = editor.content_actions()
    assert content[0][0] == "upload_file"
    assert content[0][1] == "img.jpg"


@pytest.mark.unit
def test_featured_block__calls_upload_file(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(FeaturedImageBlock(path="thumb.jpg"),))]).run(editor)
    content = editor.content_actions()
    assert content[0][0] == "upload_file"


@pytest.mark.unit
def test_heading_block__calls_insert_text(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(HeadingBlock(level=2, text="Title"),))]).run(editor)
    content = editor.content_actions()
    assert content[0] == ("insert_text", "Title", 1)


# ---------------------------------------------------------------------------
# Representative image
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_featured_block__calls_set_representative_image(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ImageBlock(path="img.jpg"), FeaturedImageBlock(path="thumb.jpg")))]).run(editor)
    assert any(a[0] == "set_rep" for a in editor.actions)


@pytest.mark.unit
def test_no_featured_block__skips_set_representative_image(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ImageBlock(path="img.jpg"), ParagraphBlock()))]).run(editor)
    assert not any(a[0] == "set_rep" for a in editor.actions)


@pytest.mark.unit
def test_featured_block__set_rep_called_after_all_content(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(FeaturedImageBlock(path="thumb.jpg"), ParagraphBlock()))]).run(editor)
    names = [a[0] for a in editor.actions]
    last_content = max(i for i, n in enumerate(names) if n in _CONTENT_ACTIONS)
    set_rep_idx  = names.index("set_rep")
    assert set_rep_idx > last_content


# ---------------------------------------------------------------------------
# Cursor movement
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_multiple_blocks__cursor_moved_between_each(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(), ParagraphBlock()))]).run(editor)
    assert any(a[0] == "cursor" for a in editor.actions)


@pytest.mark.unit
def test_single_block__cursor_not_moved(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(),))]).run(editor)
    assert not any(a[0] == "cursor" for a in editor.actions)


# ---------------------------------------------------------------------------
# Publish schedule
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_immediate_publish__schedule_at_is_none(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_publish(PublishOption(mode="immediate")).run(editor)
    publish_action = next(a for a in editor.actions if a[0] == "publish")
    assert publish_action[1] is None


@pytest.mark.unit
def test_fixed_publish__schedule_at_matches_option(editor):
    future = datetime.now(tz=KST) + timedelta(hours=2)
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_publish(PublishOption(mode="fixed", at=future)).run(editor)
    publish_action = next(a for a in editor.actions if a[0] == "publish")
    assert publish_action[1] == future
