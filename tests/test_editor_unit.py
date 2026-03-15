"""
tests/test_editor_unit.py
--------------------------
Layer 3: SmartEditorOne (Editor Shell) 테스트

SmartEditorOne이 BlogEditor ABC를 올바르게 구현하는지 검증한다.
DOM 조작 함수(browser_actions)는 test_browser_actions.py에서 별도 검증한다.

여기서 검증하는 것:
  - 각 공개 메서드가 올바른 인자를 keyboard/file_chooser에 전달한다.
  - 경계 조건(빈 문자열, 음수 index, 로그인 리다이렉트)에서 올바르게 동작한다.
  - dry_run 플래그가 publish()를 막는다.
"""

import pytest
from unittest.mock import MagicMock, call

from automator.smart_editor import SmartEditorOne


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_locator() -> MagicMock:
    loc      = MagicMock()
    loc.first = loc
    loc.last  = loc
    loc.nth   = MagicMock(return_value=loc)
    return loc


def _make_page() -> MagicMock:
    """Mock Page where frame_locator('#mainFrame') succeeds."""
    page  = MagicMock()
    frame = MagicMock()
    loc   = _make_locator()

    frame.first              = frame
    frame.locator            = MagicMock(return_value=loc)
    frame.get_by_text        = MagicMock(return_value=loc)
    frame.get_by_test_id     = MagicMock(return_value=loc)
    frame.get_by_role        = MagicMock(return_value=loc)
    frame.get_by_label       = MagicMock(return_value=loc)
    frame.get_by_placeholder = MagicMock(return_value=loc)

    page.frame_locator       = MagicMock(return_value=frame)
    page.locator             = MagicMock(return_value=loc)
    page.get_by_text         = MagicMock(return_value=loc)
    page.get_by_test_id      = MagicMock(return_value=loc)
    page.get_by_role         = MagicMock(return_value=loc)
    page.get_by_label        = MagicMock(return_value=loc)
    page.get_by_placeholder  = MagicMock(return_value=loc)
    page.frames              = []
    page.main_frame          = MagicMock()
    page.url                 = "https://blog.naver.com/test?Redirect=Write&"
    page.keyboard            = MagicMock()
    return page


WRITE_URL = "https://blog.naver.com/test?Redirect=Write&"


@pytest.fixture
def mock_page() -> MagicMock:
    return _make_page()


@pytest.fixture
def editor(mock_page) -> SmartEditorOne:
    return SmartEditorOne(mock_page, WRITE_URL)


# ===========================================================================
# 1. open()
# ===========================================================================

@pytest.mark.unit
def test_open_navigates_to_write_url(editor, mock_page):
    editor.open()
    mock_page.goto.assert_called_once_with(WRITE_URL)


@pytest.mark.unit
def test_open_raises_on_login_redirect(mock_page):
    mock_page.url = "https://nid.naver.com/nidlogin.login"
    with pytest.raises(RuntimeError, match="login"):
        SmartEditorOne(mock_page, WRITE_URL).open()


@pytest.mark.unit
def test_open_raises_on_login_keyword_in_url(mock_page):
    mock_page.url = "https://nid.naver.com/login/form"
    with pytest.raises(RuntimeError):
        SmartEditorOne(mock_page, WRITE_URL).open()


# ===========================================================================
# 2. write_title()
# ===========================================================================

@pytest.mark.unit
def test_write_title_types_correct_text(editor, mock_page):
    editor.write_title("테스트 제목")
    mock_page.keyboard.type.assert_called_once_with("테스트 제목")


@pytest.mark.unit
def test_write_title_accepts_empty_string(editor, mock_page):
    editor.write_title("")
    mock_page.keyboard.type.assert_called_once_with("")


# ===========================================================================
# 3. write_paragraph()
# ===========================================================================

@pytest.mark.unit
def test_write_paragraph_types_correct_text(editor, mock_page):
    editor.write_paragraph("본문 단락")
    mock_page.keyboard.type.assert_called_once_with("본문 단락")


@pytest.mark.unit
def test_write_paragraph_presses_enter_default(editor, mock_page):
    editor.write_paragraph("단락")
    enter_calls = [c for c in mock_page.keyboard.press.call_args_list
                   if c == call("Enter")]
    assert len(enter_calls) == 2


@pytest.mark.unit
def test_write_paragraph_presses_enter_custom(editor, mock_page):
    editor.write_paragraph("단락", newlines=1)
    enter_calls = [c for c in mock_page.keyboard.press.call_args_list
                   if c == call("Enter")]
    assert len(enter_calls) == 1


@pytest.mark.unit
def test_write_paragraph_minimum_one_enter(editor, mock_page):
    editor.write_paragraph("단락", newlines=0)
    enter_calls = [c for c in mock_page.keyboard.press.call_args_list
                   if c == call("Enter")]
    assert len(enter_calls) >= 1


# ===========================================================================
# 4. upload_image()
# ===========================================================================

@pytest.mark.unit
def test_upload_image_raises_for_missing_file(editor):
    with pytest.raises(FileNotFoundError):
        editor.upload_image("/nonexistent/image.jpg")


@pytest.mark.unit
def test_upload_image_sets_correct_file(editor, mock_page, tmp_path):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"fake")

    fc = MagicMock()
    mock_page.expect_file_chooser.return_value.__enter__ = MagicMock(return_value=fc)
    mock_page.expect_file_chooser.return_value.__exit__  = MagicMock(return_value=False)

    editor.upload_image(str(img))
    fc.value.set_files.assert_called_once_with(str(img))


# ===========================================================================
# 5. set_representative_image()
# ===========================================================================

@pytest.mark.unit
def test_set_rep_image_raises_for_negative_index(editor):
    with pytest.raises(ValueError, match="index must be >= 0"):
        editor.set_representative_image(-1)


@pytest.mark.unit
def test_set_rep_image_hovers_before_click(mock_page):
    """set_representative_image는 hover 후 locator.evaluate로 클릭한다."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.nth.return_value.evaluate = MagicMock(return_value="selected")
    SmartEditorOne(mock_page, WRITE_URL).set_representative_image(0)
    # image_block.nth(0).hover() 가 호출됐는지 확인
    loc.nth.return_value.hover.assert_called()


@pytest.mark.unit
def test_set_rep_image_raises_when_locator_evaluate_returns_not_selected(mock_page):
    """locator_dispatch_click이 'not-selected' 반환 시 RuntimeError."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.nth.return_value.evaluate = MagicMock(return_value="not-selected")
    with pytest.raises(RuntimeError, match="failed"):
        SmartEditorOne(mock_page, WRITE_URL).set_representative_image(0)


# ===========================================================================
# 6. move_cursor_to_end()
# ===========================================================================

@pytest.mark.unit
def test_move_cursor_to_end_presses_ctrl_end(editor, mock_page):
    editor.move_cursor_to_end()
    mock_page.keyboard.press.assert_any_call("Control+End")


# ===========================================================================
# 7. publish()
# ===========================================================================

@pytest.mark.unit
def test_publish_dry_run_does_not_click(mock_page):
    SmartEditorOne(mock_page, WRITE_URL, dry_run=True).publish()
    mock_page.get_by_role.return_value.click.assert_not_called()


@pytest.mark.unit
def test_publish_non_dry_run_attempts_click(mock_page):
    SmartEditorOne(mock_page, WRITE_URL, dry_run=False).publish()
    assert mock_page.get_by_role.called or mock_page.locator.called


# ===========================================================================
# open() — overlay dismissal
# ===========================================================================
# ===========================================================================

@pytest.mark.unit
def test_open_uses_dismiss_parallel_for_overlays(mock_page):
    """open()은 모든 오버레이를 dismiss_parallel로 동시에 처리한다."""
    from unittest.mock import patch

    calls = []
    def fake_dismiss_parallel(locators, timeout_ms=8_000):
        calls.append(len(locators))
        return [False] * len(locators)

    with patch("automator.smart_editor.dismiss_parallel", fake_dismiss_parallel):
        SmartEditorOne(mock_page, WRITE_URL).open()

    assert calls, "dismiss_parallel must be called at least once"
    assert max(calls) >= 2, "at least 2 locators must be passed to dismiss_parallel"
