"""
tests/test_editor_unit.py
--------------------------
Unit tests for SmartEditorOne.

Verifies that SmartEditorOne correctly translates BlogEditor method calls
into the expected Playwright API calls. All tests use mocks — no browser
is launched.

What is tested here:
  - Each BlogEditor method calls the right Playwright primitives
  - Edge cases raise the correct exception types
  - Overlay dismissal logic (popup / help panel) behaves correctly

What is NOT tested here:
  - Business ordering (that's NaverBlogJob's job → test_job_unit.py)
  - Real DOM behaviour (that's e2e → test_blog_e2e.py)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import json

from automator.smart_editor import SmartEditorOne
from automator.browser import (
    MAIN_FRAME,
    EDITOR_CONTENT,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    POPUP_CANCEL_BUTTON,
    HELP_CLOSE_BUTTON,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def editor_json(tmp_path: Path) -> Path:
    data = {
        "editor_title":    {"primary": "page.get_by_text('제목', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('제목', exact=True)",         "score": 0.42}]},
        "editor_body":     {"primary": "page.get_by_text('본문', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('본문', exact=True)",         "score": 0.42}]},
        "image_trigger":   {"primary": "page.get_by_text('사진사진 추가', exact=True)", "selectors": [{"label": "text",   "pw": "page.get_by_text('사진사진 추가', exact=True)", "score": 0.42}]},
        "publish_trigger": {"primary": "page.get_by_text('발행', exact=True)",         "selectors": [{"label": "text",   "pw": "page.get_by_text('발행', exact=True)",         "score": 0.42}]},
        "publish_confirm": {"primary": "page.get_by_test_id('seOnePublishBtn')",       "selectors": [{"label": "testid", "pw": "page.get_by_test_id('seOnePublishBtn')",       "score": 0.65}]},
        "library_close":   {"primary": "page.get_by_text('팝업 닫기', exact=True)",    "selectors": [{"label": "text",   "pw": "page.get_by_text('팝업 닫기', exact=True)",    "score": 0.42}]},
    }
    p = tmp_path / "editor.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_page() -> MagicMock:
    """
    Build a mock Page where frame_locator(MAIN_FRAME) succeeds,
    so editor_frame() always returns the iframe path.
    """
    page   = MagicMock()
    frame  = MagicMock()
    frame.first = frame

    locator = MagicMock()
    locator.first = locator

    frame.locator.return_value     = locator
    frame.get_by_text.return_value = locator
    frame.get_by_test_id.return_value = locator

    page.frame_locator.return_value = frame
    page.locator.return_value       = locator
    page.get_by_text.return_value   = locator
    page.get_by_test_id.return_value = locator

    return page


@pytest.fixture
def mock_page() -> MagicMock:
    return _make_page()


@pytest.fixture
def smart_editor(mock_page, editor_json) -> SmartEditorOne:
    return SmartEditorOne(
        page=mock_page,
        write_url="https://blog.naver.com/test?Redirect=Write&",
        editor_json=editor_json,
    )


# ===========================================================================
# open()
# ===========================================================================

@pytest.mark.unit
def test_open_navigates_to_write_url(smart_editor, mock_page):
    smart_editor.open()
    mock_page.goto.assert_called_once_with(
        "https://blog.naver.com/test?Redirect=Write&"
    )


@pytest.mark.unit
def test_open_waits_for_domcontentloaded(smart_editor, mock_page):
    smart_editor.open()
    mock_page.wait_for_load_state.assert_called_with("domcontentloaded")


@pytest.mark.unit
def test_open_probes_for_editor_content(smart_editor, mock_page):
    smart_editor.open()
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_open_dismisses_recovery_popup(editor_json):
    """복구 팝업이 나타나면 dismiss한다."""
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    popup_btn = MagicMock()
    popup_btn.first = popup_btn
    popup_btn.wait_for.return_value = None

    help_btn = MagicMock()
    help_btn.first = help_btn
    help_btn.wait_for.side_effect = Exception("no help")

    def route(sel):
        if sel == POPUP_CANCEL_BUTTON: return popup_btn
        if sel == HELP_CLOSE_BUTTON:   return help_btn
        return MagicMock()

    frame.locator.side_effect = route

    editor = SmartEditorOne(page, "https://blog.naver.com/test?Redirect=Write&",
                             editor_json)

    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        try:
            editor.open()
        except Exception:
            pass

    popup_btn.click.assert_called()


@pytest.mark.unit
def test_open_dismisses_help_panel(editor_json):
    """도움말 패널이 열려 있으면 dismiss한다."""
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    popup_btn = MagicMock()
    popup_btn.first = popup_btn
    popup_btn.wait_for.side_effect = Exception("no popup")

    help_btn = MagicMock()
    help_btn.first = help_btn
    help_btn.wait_for.return_value = None

    def route(sel):
        if sel == POPUP_CANCEL_BUTTON: return popup_btn
        if sel == HELP_CLOSE_BUTTON:   return help_btn
        return MagicMock()

    frame.locator.side_effect = route

    editor = SmartEditorOne(page, "https://blog.naver.com/test?Redirect=Write&",
                             editor_json)

    with patch("time.monotonic", side_effect=[0.0, 0.0, 999.0]):
        try:
            editor.open()
        except Exception:
            pass

    help_btn.click.assert_called_once()


# ===========================================================================
# write_title() / write_body()
# ===========================================================================

@pytest.mark.unit
def test_write_title_uses_editor_iframe(smart_editor, mock_page):
    smart_editor.write_title("테스트 제목")
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_write_title_types_correct_text(smart_editor, mock_page):
    smart_editor.write_title("입력 제목")
    mock_page.keyboard.type.assert_called_once_with("입력 제목")


@pytest.mark.unit
def test_write_body_uses_editor_iframe(smart_editor, mock_page):
    smart_editor.write_body("테스트 본문")
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_write_body_types_correct_text(smart_editor, mock_page):
    smart_editor.write_body("입력 본문")
    mock_page.keyboard.type.assert_called_once_with("입력 본문")


@pytest.mark.unit
def test_write_title_and_body_use_different_selectors(smart_editor, mock_page):
    smart_editor.write_title("제목")
    title_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    mock_page.reset_mock()

    smart_editor.write_body("본문")
    body_call = mock_page.frame_locator.return_value.first.get_by_text.call_args

    assert title_call != body_call


# ===========================================================================
# upload_image()
# ===========================================================================

@pytest.mark.unit
def test_upload_image_raises_for_missing_file(smart_editor):
    with pytest.raises(FileNotFoundError):
        smart_editor.upload_image("/no/such/file.jpg")


@pytest.mark.unit
def test_upload_image_uses_editor_iframe(smart_editor, mock_page, tmp_path):
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8")
    smart_editor.upload_image(str(img))
    mock_page.frame_locator.assert_called_with(MAIN_FRAME)


@pytest.mark.unit
def test_upload_image_closes_library_popup_if_open(smart_editor, mock_page, tmp_path):
    """파일 선택 후 라이브러리 팝업이 열리면 자동으로 닫는다."""
    img = tmp_path / "t.jpg"
    img.write_bytes(b"\xff\xd8")

    frame   = mock_page.frame_locator.return_value.first
    lib_btn = MagicMock()
    lib_btn.wait_for.return_value = None
    default_loc = MagicMock()

    def dispatch(text, **kw):
        # side_effect 내에서 frame.get_by_text를 다시 호출하면 재귀가 발생하므로
        # 기본값은 새 MagicMock을 직접 반환한다.
        return lib_btn if text == "팝업 닫기" else default_loc

    frame.get_by_text.side_effect = dispatch
    smart_editor.upload_image(str(img))
    lib_btn.click.assert_called()


# ===========================================================================
# move_cursor_to_end()
# ===========================================================================

@pytest.mark.unit
def test_move_cursor_to_end_clicks_editor_content(smart_editor, mock_page):
    smart_editor.move_cursor_to_end()
    frame = mock_page.frame_locator.return_value.first
    frame.locator.assert_any_call(EDITOR_CONTENT)


@pytest.mark.unit
def test_move_cursor_to_end_presses_ctrl_end(smart_editor, mock_page):
    smart_editor.move_cursor_to_end()
    mock_page.keyboard.press.assert_called_once_with("Control+End")


# ===========================================================================
# set_representative_image()
# ===========================================================================

def _make_page_for_rep(evaluate_return: str = "selected") -> tuple:
    page      = _make_page()
    js_frame  = MagicMock()
    js_frame.evaluate.return_value = evaluate_return
    page.main_frame = MagicMock()
    page.frames     = [page.main_frame, js_frame]
    return page, js_frame


@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(smart_editor):
    with pytest.raises(ValueError):
        smart_editor.set_representative_image(-1)


@pytest.mark.unit
def test_set_rep_image_uses_js_dispatch(editor_json):
    page, js_frame = _make_page_for_rep("selected")
    editor = SmartEditorOne(page, "https://example.com", editor_json)
    editor.set_representative_image(1)

    js_frame.evaluate.assert_called_once()
    js_code, js_args = js_frame.evaluate.call_args[0]
    assert "dispatchEvent" in js_code
    assert js_args == [REP_IMAGE_BUTTON, 1]


@pytest.mark.unit
def test_set_rep_image_raises_when_js_returns_not_selected(editor_json):
    page, _ = _make_page_for_rep("not-selected")
    editor   = SmartEditorOne(page, "https://example.com", editor_json)
    with pytest.raises(RuntimeError):
        editor.set_representative_image(0)


# ===========================================================================
# publish()
# ===========================================================================

@pytest.mark.unit
def test_publish_tries_page_level_trigger_first(smart_editor, mock_page):
    smart_editor.publish()
    mock_page.get_by_text.assert_any_call("발행", exact=True)


@pytest.mark.unit
def test_publish_trigger_clicks_when_found(smart_editor, mock_page):
    smart_editor.publish()
    mock_page.get_by_text.return_value.click.assert_called()


@pytest.mark.unit
def test_publish_confirm_uses_test_id(smart_editor, mock_page):
    smart_editor.publish()
    mock_page.get_by_test_id.assert_called_with("seOnePublishBtn")


@pytest.mark.unit
def test_publish_trigger_falls_back_to_iframe(editor_json):
    """page 레벨 발행 버튼 실패 시 iframe fallback을 사용한다."""
    page  = _make_page()
    frame = page.frame_locator.return_value.first

    # page-level trigger fails
    page_loc = MagicMock()
    page_loc.wait_for.side_effect = Exception("not on page")
    page.get_by_text.return_value = page_loc

    # iframe trigger succeeds
    frame_loc = MagicMock()
    frame.get_by_text.return_value = frame_loc

    editor = SmartEditorOne(page, "https://example.com", editor_json)
    editor.publish()

    frame.get_by_text.assert_called()
    frame_loc.click.assert_called()
