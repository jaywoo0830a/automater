"""
tests/test_post_step.py
------------------------
PostStep.execute() — each step calls the correct BlogEditor primitive.
PostStep properties — needs_upload_delay, marks_representative.
"""

import pytest
from unittest.mock import MagicMock

from automator.editor import (
    BlogEditor,
    ParagraphStep, ImageStep, FeaturedImageStep, HeadingStep,
    ListStep, QuoteStep,
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


def test_featured_image_step_calls_upload_file(mock_editor):
    step = FeaturedImageStep(path="/some/thumb.jpg")
    step.execute(mock_editor)
    mock_editor.upload_file.assert_called_once_with("/some/thumb.jpg")


def test_heading_step_calls_insert_text(mock_editor):
    step = HeadingStep(level=2, text="Section title")
    step.execute(mock_editor)
    mock_editor.insert_text.assert_called_once_with("Section title", 1)


def test_list_step_calls_insert_text(mock_editor):
    step = ListStep(text="- item1\n- item2")
    step.execute(mock_editor)
    mock_editor.insert_text.assert_called_once_with("- item1\n- item2", 2)


def test_quote_step_calls_insert_text(mock_editor):
    step = QuoteStep(text="wise words")
    step.execute(mock_editor)
    mock_editor.insert_text.assert_called_once_with("wise words", 2)


# ---------------------------------------------------------------------------
# Orchestration properties
# ---------------------------------------------------------------------------

def test_paragraph_step_no_upload_delay():
    assert not ParagraphStep(text="x").needs_upload_delay


def test_image_step_needs_upload_delay():
    assert ImageStep(path="x").needs_upload_delay


def test_featured_image_step_needs_upload_delay():
    assert FeaturedImageStep(path="x").needs_upload_delay


def test_paragraph_step_not_representative():
    assert not ParagraphStep(text="x").marks_representative


def test_image_step_not_representative():
    assert not ImageStep(path="x").marks_representative


def test_featured_image_step_marks_representative():
    assert FeaturedImageStep(path="x").marks_representative


def test_heading_step_no_upload_delay():
    assert not HeadingStep(level=1, text="x").needs_upload_delay


def test_heading_step_not_representative():
    assert not HeadingStep(level=1, text="x").marks_representative
