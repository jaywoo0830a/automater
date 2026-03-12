"""
tests/test_job_unit.py
----------------------
Unit tests for NaverBlogJob.

Uses MockEditor (a BlogEditor implementation that records calls) so every
test runs without a browser. No Playwright, no DOM, no network.

Tests verify:
  - validation rejects bad content before the editor is touched
  - the publish sequence calls editor methods in the correct order
  - image upload and representative image selection are wired correctly
  - run() returns True on success and False on editor failure
"""

import pytest
from automator.editor import BlogEditor, PostContent
from automator.job import NaverBlogJob


# ===========================================================================
# MockEditor — records every call made by NaverBlogJob
# ===========================================================================

class MockEditor(BlogEditor):
    """
    BlogEditor implementation that records method calls.

    Tests inspect ``actions`` to verify ordering and arguments without
    needing a browser.
    """

    def __init__(self, fail_on: str | None = None) -> None:
        """
        Args:
            fail_on: If set, the named method raises RuntimeError when called.
                     Used to test NaverBlogJob's error handling.
        """
        self.actions: list[tuple] = []
        self._fail_on = fail_on

    def _record(self, name: str, *args) -> None:
        if self._fail_on == name:
            raise RuntimeError(f"MockEditor: forced failure on {name!r}")
        self.actions.append((name, *args))

    def open(self)                          -> None: self._record("open")
    def write_title(self, title: str)       -> None: self._record("write_title", title)
    def write_body(self, body: str)         -> None: self._record("write_body", body)
    def upload_image(self, path: str)       -> None: self._record("upload_image", path)
    def set_representative_image(self, idx) -> None: self._record("set_representative_image", idx)
    def move_cursor_to_end(self)            -> None: self._record("move_cursor_to_end")
    def publish(self)                       -> None: self._record("publish")


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def editor() -> MockEditor:
    return MockEditor()


@pytest.fixture
def job(editor: MockEditor) -> NaverBlogJob:
    return NaverBlogJob(editor)


@pytest.fixture
def minimal_content() -> PostContent:
    return PostContent(title="제목", body="본문")


@pytest.fixture
def content_with_images() -> PostContent:
    return PostContent(
        title="제목",
        body="본문",
        images=["a.jpg", "b.jpg", "c.jpg"],
        representative_image=1,
    )


# ===========================================================================
# PostContent — value object
# ===========================================================================

@pytest.mark.unit
def test_post_content_stores_title_and_body():
    c = PostContent(title="T", body="B")
    assert c.title == "T" and c.body == "B"


@pytest.mark.unit
def test_post_content_images_default_empty():
    assert PostContent(title="T", body="B").images == []


@pytest.mark.unit
def test_post_content_representative_image_default_none():
    assert PostContent(title="T", body="B").representative_image is None


@pytest.mark.unit
def test_post_content_tags_default_empty():
    assert PostContent(title="T", body="B").tags == []


# ===========================================================================
# Validation — errors raised before the editor is ever touched
# ===========================================================================

@pytest.mark.unit
def test_validate_raises_on_empty_title(job):
    with pytest.raises(ValueError, match="title"):
        job.validate(PostContent(title="", body="본문"))


@pytest.mark.unit
def test_validate_raises_on_whitespace_title(job):
    with pytest.raises(ValueError, match="title"):
        job.validate(PostContent(title="   ", body="본문"))


@pytest.mark.unit
def test_validate_raises_on_empty_body(job):
    with pytest.raises(ValueError, match="body"):
        job.validate(PostContent(title="제목", body=""))


@pytest.mark.unit
def test_validate_raises_on_rep_image_without_images(job):
    with pytest.raises(ValueError, match="no images"):
        job.validate(PostContent(title="제목", body="본문", representative_image=0))


@pytest.mark.unit
def test_validate_raises_on_rep_image_out_of_range(job):
    with pytest.raises(ValueError, match="out of range"):
        job.validate(PostContent(title="제목", body="본문", images=["a.jpg"], representative_image=1))


@pytest.mark.unit
def test_validate_does_not_call_editor_on_failure(editor, job):
    """Validation must fire before the editor is opened."""
    try:
        job.run(PostContent(title="", body="본문"))
    except ValueError:
        pass
    assert editor.actions == [], "editor must not be called when validation fails"


# ===========================================================================
# Publish sequence — ordering
# ===========================================================================

@pytest.mark.unit
def test_run_returns_true_on_success(job, minimal_content):
    assert job.run(minimal_content) is True


@pytest.mark.unit
def test_run_opens_editor_first(editor, job, minimal_content):
    job.run(minimal_content)
    assert editor.actions[0] == ("open",)


@pytest.mark.unit
def test_run_writes_title_before_body(editor, job, minimal_content):
    job.run(minimal_content)
    names = [a[0] for a in editor.actions]
    assert names.index("write_title") < names.index("write_body")


@pytest.mark.unit
def test_run_writes_correct_title(editor, job, minimal_content):
    job.run(minimal_content)
    assert ("write_title", "제목") in editor.actions


@pytest.mark.unit
def test_run_writes_correct_body(editor, job, minimal_content):
    job.run(minimal_content)
    assert ("write_body", "본문") in editor.actions


@pytest.mark.unit
def test_run_publishes_last(editor, job, minimal_content):
    job.run(minimal_content)
    assert editor.actions[-1] == ("publish",)


@pytest.mark.unit
def test_run_returns_false_when_editor_raises(editor):
    failing_job = NaverBlogJob(MockEditor(fail_on="open"))
    assert failing_job.run(PostContent(title="제목", body="본문")) is False


# ===========================================================================
# Image upload sequence
# ===========================================================================

@pytest.mark.unit
def test_single_image_is_uploaded(editor, job):
    job.run(PostContent(title="제목", body="본문", images=["x.jpg"]))
    assert ("upload_image", "x.jpg") in editor.actions


@pytest.mark.unit
def test_no_move_cursor_before_first_image(editor, job):
    """move_cursor_to_end must NOT be called before the first upload."""
    job.run(PostContent(title="제목", body="본문", images=["a.jpg"]))
    names = [a[0] for a in editor.actions]
    upload_idx = names.index("upload_image")
    cursor_indices = [i for i, n in enumerate(names) if n == "move_cursor_to_end"]
    assert all(c > upload_idx for c in cursor_indices), (
        "move_cursor_to_end must not appear before the first upload"
    )


@pytest.mark.unit
def test_cursor_moved_between_images(editor, job, content_with_images):
    """move_cursor_to_end must appear between consecutive uploads."""
    job.run(content_with_images)
    names = [a[0] for a in editor.actions]
    upload_positions = [i for i, n in enumerate(names) if n == "upload_image"]
    cursor_positions = [i for i, n in enumerate(names) if n == "move_cursor_to_end"]

    # 3 images → 2 cursor moves, each between consecutive uploads
    assert len(cursor_positions) == 2
    assert upload_positions[0] < cursor_positions[0] < upload_positions[1]
    assert upload_positions[1] < cursor_positions[1] < upload_positions[2]


@pytest.mark.unit
def test_all_images_uploaded_in_order(editor, job, content_with_images):
    job.run(content_with_images)
    uploaded = [a[1] for a in editor.actions if a[0] == "upload_image"]
    assert uploaded == ["a.jpg", "b.jpg", "c.jpg"]


@pytest.mark.unit
def test_representative_image_set_after_all_uploads(editor, job, content_with_images):
    job.run(content_with_images)
    names = [a[0] for a in editor.actions]
    last_upload = max(i for i, n in enumerate(names) if n == "upload_image")
    rep_idx = names.index("set_representative_image")
    assert rep_idx > last_upload


@pytest.mark.unit
def test_representative_image_correct_index(editor, job, content_with_images):
    job.run(content_with_images)
    rep_calls = [a for a in editor.actions if a[0] == "set_representative_image"]
    assert rep_calls == [("set_representative_image", 1)]


@pytest.mark.unit
def test_no_representative_image_when_not_requested(editor, job):
    job.run(PostContent(title="제목", body="본문", images=["a.jpg"]))
    rep_calls = [a for a in editor.actions if a[0] == "set_representative_image"]
    assert rep_calls == []


@pytest.mark.unit
def test_no_images_no_upload_calls(editor, job, minimal_content):
    job.run(minimal_content)
    upload_calls = [a for a in editor.actions if a[0] == "upload_image"]
    assert upload_calls == []
