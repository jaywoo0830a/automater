"""
tests/test_editor_unit.py
--------------------------
Unit tests for SmartEditorOne.

Verifies that each BlogEditor method calls the right Playwright primitives.
No browser is launched — all Playwright objects are mocks.
"""

import pytest
from unittest.mock import MagicMock, patch

from automator.smart_editor import SmartEditorOne
from automator.browser import (
    MAIN_FRAME, EDITOR_CONTENT, UPLOADED_IMAGE, IMAGE_COMPONENT,
    REP_IMAGE_BUTTON, REP_IMAGE_BUTTON_SELECTED,
    POPUP_CANCEL_BUTTON, HELP_CLOSE_BUTTON,
)


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_page() -> MagicMock:
    """Build a mock Page where frame_locator(MAIN_FRAME) succeeds."""
    page  = MagicMock()
    frame = MagicMock()
    frame.first = frame
    loc = MagicMock()
    loc.first = loc
    frame.locator.return_value        = loc
    frame.get_by_text.return_value    = loc
    frame.get_by_test_id.return_value = loc
    frame.get_by_role.return_value    = loc
    frame.get_by_label.return_value   = loc
    page.frame_locator.return_value   = frame
    page.locator.return_value         = loc
    page.get_by_text.return_value     = loc
    page.get_by_test_id.return_value  = loc
    page.get_by_role.return_value     = loc
    page.get_by_label.return_value    = loc
    return page


@pytest.fixture
def mock_page() -> MagicMock:
    return _make_page()


@pytest.fixture
def editor(mock_page) -> SmartEditorOne:
    return SmartEditorOne(mock_page, "https://blog.naver.com/test?Redirect=Write&")


# ===========================================================================
# open()
# ===========================================================================

@pytest.mark.unit
def test_open_navigates_to_write_url(editor, mock_page):
    editor.open()
    mock_page.goto.assert_called_once_with("https://blog.naver.com/test?Redirect=Write&")


@pytest.mark.unit
def test_open_waits_for_domcontentloaded(editor, mock_page):
    editor.open()
    mock_page.wait_for_load_state.assert_called_with("domcontentloaded")


@pytest.mark.unit
def test_open_probes_for_editor_iframe(editor, mock_page):
    editor.open()
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_open_dismisses_recovery_popup():
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    popup = MagicMock()
    popup.first = popup
    popup.wait_for.return_value = None

    help_btn = MagicMock()
    help_btn.first = help_btn
    help_btn.wait_for.side_effect = Exception("no help")

    def route(sel):
        if sel == POPUP_CANCEL_BUTTON: return popup
        if sel == HELP_CLOSE_BUTTON:   return help_btn
        return MagicMock()

    frame.locator.side_effect = route

    e = SmartEditorOne(page, "https://example.com")
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        try: e.open()
        except Exception: pass

    popup.click.assert_called()


@pytest.mark.unit
def test_open_dismisses_help_panel():
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    popup = MagicMock()
    popup.first = popup
    popup.wait_for.side_effect = Exception("no popup")

    help_btn = MagicMock()
    help_btn.first = help_btn
    help_btn.wait_for.return_value = None

    def route(sel):
        if sel == POPUP_CANCEL_BUTTON: return popup
        if sel == HELP_CLOSE_BUTTON:   return help_btn
        return MagicMock()

    frame.locator.side_effect = route

    e = SmartEditorOne(page, "https://example.com")
    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        try: e.open()
        except Exception: pass

    help_btn.click.assert_called_once()


# ===========================================================================
# write_title() / write_paragraph()
# ===========================================================================

@pytest.mark.unit
def test_write_title_uses_editor_iframe(editor, mock_page):
    editor.write_title("제목")
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_write_title_types_correct_text(editor, mock_page):
    editor.write_title("입력 제목")
    mock_page.keyboard.type.assert_called_once_with("입력 제목")


@pytest.mark.unit
def test_write_paragraph_uses_editor_iframe(editor, mock_page):
    editor.write_paragraph("단락")
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_write_paragraph_types_correct_text(editor, mock_page):
    editor.write_paragraph("입력 단락")
    mock_page.keyboard.type.assert_called_once_with("입력 단락")


@pytest.mark.unit
def test_write_paragraph_presses_enter_default(editor, mock_page):
    # default newlines=2 → Enter pressed twice
    editor.write_paragraph("단락")
    enter_calls = [
        c for c in mock_page.keyboard.press.call_args_list
        if c.args == ("Enter",)
    ]
    assert len(enter_calls) == 2


@pytest.mark.unit
def test_write_paragraph_presses_enter_custom(editor, mock_page):
    # newlines=3 → Enter pressed three times
    editor.write_paragraph("단락", newlines=3)
    enter_calls = [
        c for c in mock_page.keyboard.press.call_args_list
        if c.args == ("Enter",)
    ]
    assert len(enter_calls) == 3


# ===========================================================================
# upload_image()
# ===========================================================================

@pytest.mark.unit
def test_upload_image_raises_for_missing_file(editor):
    with pytest.raises(FileNotFoundError):
        editor.upload_image("/no/such/file.jpg")


@pytest.mark.unit
def test_upload_image_uses_editor_iframe(editor, mock_page, tmp_path):
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8")
    editor.upload_image(str(img))
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_upload_image_closes_library_popup_if_open(editor, mock_page, tmp_path):
    """라이브러리 팝업이 나타나면 자동으로 닫는다."""
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8")

    frame   = mock_page.frame_locator.return_value.first
    lib_btn = MagicMock()
    lib_btn.wait_for.return_value = None
    default = MagicMock()

    def route(*args, **kw):
        # get_by_role("button", name="팝업 닫기") — name arrives as a keyword
        label = kw.get("name") or (args[0] if args else "")
        return lib_btn if label == "팝업 닫기" else default

    frame.get_by_role.side_effect = route
    editor.upload_image(str(img))
    lib_btn.click.assert_called()


# ===========================================================================
# move_cursor_to_end()
# ===========================================================================

@pytest.mark.unit
def test_move_cursor_to_end_clicks_editor_content(editor, mock_page):
    editor.move_cursor_to_end()
    frame = mock_page.frame_locator.return_value.first
    frame.locator.assert_any_call(EDITOR_CONTENT)


@pytest.mark.unit
def test_move_cursor_to_end_presses_ctrl_end(editor, mock_page):
    editor.move_cursor_to_end()
    mock_page.keyboard.press.assert_called_once_with("Control+End")


# ===========================================================================
# set_representative_image()
# ===========================================================================

def _make_page_for_rep(evaluate_return: str = "selected"):
    page     = _make_page()
    js_frame = MagicMock()
    js_frame.evaluate.return_value = evaluate_return
    page.main_frame = MagicMock()
    page.frames     = [page.main_frame, js_frame]
    return page, js_frame


@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(editor):
    with pytest.raises(ValueError):
        editor.set_representative_image(-1)


@pytest.mark.unit
def test_set_rep_image_uses_js_dispatch():
    page, js_frame = _make_page_for_rep("selected")
    e = SmartEditorOne(page, "https://example.com")
    e.set_representative_image(1)
    js_frame.evaluate.assert_called_once()
    _, js_args = js_frame.evaluate.call_args[0]
    assert js_args == [REP_IMAGE_BUTTON, 1]


@pytest.mark.unit
def test_set_rep_image_raises_when_not_selected():
    page, _ = _make_page_for_rep("not-selected")
    e = SmartEditorOne(page, "https://example.com")
    with pytest.raises(RuntimeError):
        e.set_representative_image(0)


# ===========================================================================
# publish()
# ===========================================================================

@pytest.mark.unit
def test_publish_tries_page_level_trigger_first(editor, mock_page):
    editor.publish()
    mock_page.get_by_role.assert_any_call("button", name="발행")


@pytest.mark.unit
def test_publish_trigger_clicks_when_found(editor, mock_page):
    editor.publish()
    mock_page.get_by_role.return_value.click.assert_called()


@pytest.mark.unit
def test_publish_confirm_uses_test_id(editor, mock_page):
    editor.publish()
    mock_page.get_by_test_id.assert_called_with("seOnePublishBtn")


@pytest.mark.unit
def test_publish_falls_back_to_iframe_on_failure():
    """page 레벨 발행 버튼 실패 시 iframe fallback을 사용한다."""
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    page_loc = MagicMock()
    page_loc.wait_for.side_effect = Exception("not on page")
    page.get_by_role.return_value = page_loc

    frame_loc = MagicMock()
    frame.get_by_role.return_value = frame_loc

    e = SmartEditorOne(page, "https://example.com")
    e.publish()

    frame.get_by_role.assert_called()
    frame_loc.click.assert_called()
