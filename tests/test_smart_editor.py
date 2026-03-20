"""
tests/test_smart_editor.py
---------------------------
SmartEditorOne — BlogEditor primitive wiring via MagicMock (no browser).
"""

import pytest
from unittest.mock import MagicMock, patch

from automator.smart_editor import SmartEditorOne
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
def test_open_navigates_to_write_url(editor, mock_page):
    with patch.object(editor, "_wait_for_editor_ready"):
        editor.open()
    mock_page.goto.assert_called_once_with(_WRITE_URL)


@pytest.mark.unit
def test_open_raises_on_login_redirect(editor, mock_page):
    mock_page.url = "https://nid.naver.com/nidlogin.login"
    with patch.object(editor, "_wait_for_editor_ready"), \
         pytest.raises(RuntimeError, match="login"):
        editor.open()


@pytest.mark.unit
def test_open_raises_on_login_keyword_in_url(editor, mock_page):
    mock_page.url = "https://naver.com?redirect=login&next=..."
    with patch.object(editor, "_wait_for_editor_ready"), \
         pytest.raises(RuntimeError, match="login"):
        editor.open()


# ---------------------------------------------------------------------------
# insert_text()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_insert_text_calls_keyboard_type(editor, mock_page):
    with patch.object(editor, "_frame") as mock_frame, \
         patch.object(editor, "_sel") as mock_sel:
        locator = MagicMock()
        mock_sel.return_value.locator.return_value.last = locator
        editor.insert_text("paragraph text", 2)
    mock_page.keyboard.type.assert_called_once_with("paragraph text")


# ---------------------------------------------------------------------------
# upload_file()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_upload_file_raises_for_missing_file(editor):
    with pytest.raises(FileNotFoundError):
        editor.upload_file("/nonexistent/image.jpg")


# ---------------------------------------------------------------------------
# set_representative_image()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(editor):
    with pytest.raises(ValueError):
        editor.set_representative_image(-1)


# ---------------------------------------------------------------------------
# publish()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_publish_dry_run_opens_popover_but_skips_confirm(editor, mock_page):
    with patch.object(editor, "_click_publish_trigger"), \
         patch.object(editor, "_click_publish_confirm") as mock_confirm:
        editor.publish(schedule_at=None)
    mock_confirm.assert_not_called()


# ---------------------------------------------------------------------------
# _round_minute_to_10()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_round_minute_to_10_floors_to_nearest_ten():
    assert SmartEditorOne._round_minute_to_10(0)  == "00"
    assert SmartEditorOne._round_minute_to_10(9)  == "00"
    assert SmartEditorOne._round_minute_to_10(10) == "10"
    assert SmartEditorOne._round_minute_to_10(59) == "50"
