"""
tests/test_job_execution.py
----------------------------
PostingJob.run() — 에디터 호출 순서와 흐름 검증.

conftest.py 의 mock_paragraph_generator autouse fixture 덕분에
실제 Gemini API 호출 없이 모든 테스트가 실행된다.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from automator.editor import (
    BlogEditor,
    ParagraphStep, ImageStep, ThumbnailStep, PostStep,
)
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption,
    ParagraphBlock, ImageBlock, FeaturedImageBlock, Section,
    PublishOption, KST,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


class _RecordingEditor(BlogEditor):
    """호출 순서와 인자를 기록하는 테스트용 에디터."""

    def __init__(self):
        self.actions: list[tuple] = []

    def _rec(self, name, *args):
        self.actions.append((name, *args))

    def open(self)                         -> None: self._rec("open")
    def write_title(self, t)               -> None: self._rec("write_title", t)
    def execute(self, step: PostStep)      -> None: self._rec("execute", step)
    def set_representative_image(self, i)  -> None: self._rec("set_rep", i)
    def move_cursor_to_end(self)           -> None: self._rec("cursor_end")
    def publish(self, schedule_at=None)    -> None: self._rec("publish", schedule_at)


@pytest.fixture
def editor():
    return _RecordingEditor()


def _base_job():
    return PostingJob.for_account(_account())


# ---------------------------------------------------------------------------
# 기본 호출 순서
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_open_is_called_before_write_title(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    names = [a[0] for a in editor.actions]
    assert names.index("open") < names.index("write_title")


@pytest.mark.unit
def test_write_title_is_called_before_any_execute(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(),))]).run(editor)
    names = [a[0] for a in editor.actions]
    assert names.index("write_title") < names.index("execute")


@pytest.mark.unit
def test_publish_is_always_the_last_action(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    assert editor.actions[-1][0] == "publish"


# ---------------------------------------------------------------------------
# 빈 body 처리
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_empty_body__generates_one_stub_paragraph(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    exec_steps = [a[1] for a in editor.actions if a[0] == "execute"]
    assert len(exec_steps) == 1
    assert isinstance(exec_steps[0], ParagraphStep)


@pytest.mark.unit
def test_empty_body__still_calls_publish(editor):
    _base_job().with_title(TitleOption(fixed_title="T")).run(editor)
    assert any(a[0] == "publish" for a in editor.actions)


# ---------------------------------------------------------------------------
# Block → PostStep 변환 및 순서
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

    step_types = [
        type(a[1]).__name__
        for a in editor.actions if a[0] == "execute"
    ]
    assert step_types == ["ImageStep", "ParagraphStep", "ThumbnailStep"]


@pytest.mark.unit
def test_text_block__produces_paragraph_step(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(newlines=3),))]).run(editor)
    steps = [a[1] for a in editor.actions if a[0] == "execute"]
    assert isinstance(steps[0], ParagraphStep)
    assert steps[0].newlines == 3


@pytest.mark.unit
def test_image_block__produces_image_step(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ImageBlock(path="img.jpg"),))]).run(editor)
    steps = [a[1] for a in editor.actions if a[0] == "execute"]
    assert isinstance(steps[0], ImageStep)
    assert steps[0].path == "img.jpg"


@pytest.mark.unit
def test_featured_block__produces_thumbnail_step(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(FeaturedImageBlock(path="thumb.jpg"),))]).run(editor)
    steps = [a[1] for a in editor.actions if a[0] == "execute"]
    assert isinstance(steps[0], ThumbnailStep)


# ---------------------------------------------------------------------------
# 대표 이미지 지정
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
def test_featured_block__set_rep_called_after_all_executes(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(FeaturedImageBlock(path="thumb.jpg"), ParagraphBlock()))]).run(editor)
    names = [a[0] for a in editor.actions]
    last_execute = max(i for i, n in enumerate(names) if n == "execute")
    set_rep_idx  = names.index("set_rep")
    assert set_rep_idx > last_execute


# ---------------------------------------------------------------------------
# 커서 이동
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_multiple_blocks__cursor_moved_between_each(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(), ParagraphBlock()))]).run(editor)
    assert any(a[0] == "cursor_end" for a in editor.actions)


@pytest.mark.unit
def test_single_block__cursor_not_moved(editor):
    _base_job().with_title(TitleOption(fixed_title="T")) \
               .with_body([Section(blocks=(ParagraphBlock(),))]).run(editor)
    assert not any(a[0] == "cursor_end" for a in editor.actions)


# ---------------------------------------------------------------------------
# 발행 스케줄
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
