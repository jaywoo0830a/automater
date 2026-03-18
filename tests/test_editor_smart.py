"""
tests/test_editor_smart.py
---------------------------
SmartEditorOne — BlogEditor 구현체의 DOM 조작 검증.

모든 Playwright 상호작용은 MagicMock 으로 대체되므로
실제 브라우저 없이 실행된다.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from automator.smart_editor import SmartEditorOne
from automator.editor import ParagraphStep, ImageStep, ThumbnailStep
from automator.options import KST


_WRITE_URL = "https://blog.naver.com/test?Redirect=Write&"


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.url = _WRITE_URL
    page.frame_locator.return_value.locator.return_value = MagicMock()
    return page


@pytest.fixture
def editor(mock_page):
    return SmartEditorOne(mock_page, _WRITE_URL, dry_run=True)


# ---------------------------------------------------------------------------
# open()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_open__navigates_to_write_url(editor, mock_page):
    with patch.object(editor, "_wait_for_editor_ready"):
        editor.open()
    mock_page.goto.assert_called_once_with(_WRITE_URL)


@pytest.mark.unit
def test_open__raises_on_login_redirect(editor, mock_page):
    mock_page.url = "https://nid.naver.com/nidlogin.login"
    with patch.object(editor, "_wait_for_editor_ready"), \
         pytest.raises(RuntimeError, match="login"):
        editor.open()


@pytest.mark.unit
def test_open__raises_on_login_keyword_in_url(editor, mock_page):
    mock_page.url = "https://naver.com?redirect=login&next=..."
    with patch.object(editor, "_wait_for_editor_ready"), \
         pytest.raises(RuntimeError, match="login"):
        editor.open()


# ---------------------------------------------------------------------------
# write_title()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_execute_paragraph_step__types_correct_text(editor, mock_page):
    with patch.object(editor, "_write_paragraph") as mock_wp:
        editor.execute(ParagraphStep(text="본문 단락", newlines=2))
    mock_wp.assert_called_once_with("본문 단락", newlines=2)


@pytest.mark.unit
def test_execute_paragraph_step__passes_newlines(editor, mock_page):
    with patch.object(editor, "_write_paragraph") as mock_wp:
        editor.execute(ParagraphStep(text="단락", newlines=1))
    _, kwargs = mock_wp.call_args
    assert kwargs.get("newlines") == 1


# ---------------------------------------------------------------------------
# execute() — ImageStep / ThumbnailStep
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_execute_image_step__raises_for_missing_file(editor):
    with pytest.raises(FileNotFoundError):
        editor.execute(ImageStep(path="/nonexistent/image.jpg"))


@pytest.mark.unit
def test_execute_image_step__uploads_correct_file(editor, mock_page, tmp_path):
    img = tmp_path / "img.jpg"
    img.write_bytes(b"fake-jpeg")
    with patch.object(editor, "_upload_image") as mock_up:
        editor.execute(ImageStep(path=str(img)))
    mock_up.assert_called_once_with(str(img))


@pytest.mark.unit
def test_execute_thumbnail_step__uploads_correct_file(editor, mock_page, tmp_path):
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"fake-jpeg")
    with patch.object(editor, "_upload_image") as mock_up:
        editor.execute(ThumbnailStep(path=str(thumb)))
    mock_up.assert_called_once_with(str(thumb))


# ---------------------------------------------------------------------------
# set_representative_image()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_rep_image__raises_for_negative_index(editor):
    with pytest.raises(ValueError):
        editor.set_representative_image(-1)


# ---------------------------------------------------------------------------
# move_cursor_to_end()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_publish_dry_run__opens_popover_but_skips_confirm(editor, mock_page):
    with patch.object(editor, "_click_publish_trigger"), \
         patch.object(editor, "_click_publish_confirm") as mock_confirm:
        editor.publish(schedule_at=None)
    mock_confirm.assert_not_called()


# ---------------------------------------------------------------------------
# 스케줄 발행 유틸리티
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_round_minute_to_10__floors_to_nearest_ten():
    assert SmartEditorOne._round_minute_to_10(0)  == "00"
    assert SmartEditorOne._round_minute_to_10(9)  == "00"
    assert SmartEditorOne._round_minute_to_10(10) == "10"
    assert SmartEditorOne._round_minute_to_10(59) == "50"
