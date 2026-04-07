"""
tests/test_post_step.py
------------------------
PostStep.execute() — each step calls the correct BlogEditor primitive.
"""

import pytest
from unittest.mock import MagicMock

from automator.editor import (
    BlogEditor,
    ParagraphStep, ImageStep, FeaturedImageStep, HeadingStep,
    ListStep, QuoteStep, DividerStep,
)


@pytest.fixture
def mock_editor():
    return MagicMock(spec=BlogEditor)


# ---------------------------------------------------------------------------
# execute() dispatches to the correct primitive
# ---------------------------------------------------------------------------

def test_paragraph_step_calls_insert_text(mock_editor):
    step = ParagraphStep(text="test text", newlines=3)
    step.execute(mock_editor)
    mock_editor.insert_text.assert_called_once_with("test text", 3)


def test_image_step_calls_upload_file(mock_editor):
    step = ImageStep(path="/some/image.jpg")
    step.execute(mock_editor)
    mock_editor.upload_file.assert_called_once_with("/some/image.jpg")


def test_image_step_calls_insert_link_when_link_set(mock_editor):
    step = ImageStep(path="/some/image.jpg", link="https://example.com")
    step.execute(mock_editor)
    mock_editor.upload_file.assert_called_once_with("/some/image.jpg")
    mock_editor.insert_link.assert_called_once_with("https://example.com")


def test_image_step_skips_insert_link_when_empty(mock_editor):
    step = ImageStep(path="/some/image.jpg")
    step.execute(mock_editor)
    mock_editor.insert_link.assert_not_called()


def test_featured_image_step_calls_upload_file(mock_editor):
    step = FeaturedImageStep(path="/some/thumb.jpg")
    step.execute(mock_editor)
    mock_editor.upload_file.assert_called_once_with("/some/thumb.jpg")


def test_featured_image_step_calls_insert_link_when_link_set(mock_editor):
    step = FeaturedImageStep(path="/some/thumb.jpg", link="https://example.com")
    step.execute(mock_editor)
    mock_editor.insert_link.assert_called_once_with("https://example.com")


def test_heading_step_calls_insert_heading(mock_editor):
    step = HeadingStep(level=2, text="Section title")
    step.execute(mock_editor)
    mock_editor.insert_heading.assert_called_once_with("Section title", 2)


def test_heading_step_passes_level(mock_editor):
    step = HeadingStep(level=3, text="Sub section")
    step.execute(mock_editor)
    mock_editor.insert_heading.assert_called_once_with("Sub section", 3)


def test_list_step_calls_insert_list(mock_editor):
    step = ListStep(items=("item1", "item2"))
    step.execute(mock_editor)
    mock_editor.insert_list.assert_called_once_with(["item1", "item2"], False)


def test_list_step_ordered_calls_insert_list(mock_editor):
    step = ListStep(items=("a", "b"), ordered=True)
    step.execute(mock_editor)
    mock_editor.insert_list.assert_called_once_with(["a", "b"], True)


def test_quote_step_calls_insert_quote(mock_editor):
    step = QuoteStep(text="wise words")
    step.execute(mock_editor)
    mock_editor.insert_quote.assert_called_once_with("wise words", 1)


def test_quote_step_with_type(mock_editor):
    step = QuoteStep(text="wise", type=4)
    step.execute(mock_editor)
    mock_editor.insert_quote.assert_called_once_with("wise", 4)


def test_divider_step_calls_insert_divider(mock_editor):
    step = DividerStep()
    step.execute(mock_editor)
    mock_editor.insert_divider.assert_called_once_with(2)


def test_divider_step_with_type(mock_editor):
    step = DividerStep(type=5)
    step.execute(mock_editor)
    mock_editor.insert_divider.assert_called_once_with(5)

