"""
tests/test_browser_actions.py
------------------------------
Layer 2: Browser Actions 단독 테스트

원칙:
  - 함수당 성공/실패 두 경로 + 비자명한 계약(never raises, 특수 반환값)만 검증
  - 단순 위임, 빈 리스트, 자명한 엣지 케이스는 생략
  - 타이밍 기반 테스트 없음
"""

import pytest
from unittest.mock import MagicMock

from automator.browser_actions import (
    wait_until_visible, wait_until_hidden, wait_until_count,
    wait_for_url_contains, wait_any_visible, wait_all_visible,
    click_if_visible, click_polling, click_nth,
    fill, fill_and_submit, type_text, clear_and_fill,
    press_key, type_and_press,
    select_option_by_value, hover_if_visible,
    is_visible, is_checked, is_disabled, has_class, get_count,
    get_text, get_attribute, get_all_texts,
    scroll_into_view, scroll_to_bottom, upload_file,
    any_visible, all_visible,
    dismiss, dismiss_polling, dismiss_parallel,
    click_parallel, fill_parallel,
    get_texts_parallel, get_attributes_parallel,
    locator_dispatch_click, js_dispatch_click,
    js_evaluate, js_scroll_into_view,
    find_editor_frame, find_js_frame,
)


def _loc(visible: bool = True) -> MagicMock:
    loc = MagicMock()
    loc.wait_for = MagicMock(
        side_effect=None if visible else Exception("timeout")
    )
    return loc


# ===========================================================================
# Waiting — 계약: never raises, True/False 반환
# ===========================================================================

def test_wait_until_visible_success():
    assert wait_until_visible(_loc(True)) is True

def test_wait_until_visible_timeout():
    assert wait_until_visible(_loc(False)) is False

def test_wait_until_visible_never_raises():
    loc = MagicMock()
    loc.wait_for = MagicMock(side_effect=RuntimeError("crash"))
    assert wait_until_visible(loc) is False


def test_wait_until_hidden_success():
    assert wait_until_hidden(_loc(True)) is True

def test_wait_until_hidden_timeout():
    assert wait_until_hidden(_loc(False)) is False

def test_wait_until_hidden_never_raises():
    loc = MagicMock()
    loc.wait_for = MagicMock(side_effect=RuntimeError("crash"))
    assert wait_until_hidden(loc) is False


def test_wait_until_count_matches():
    loc = MagicMock()
    loc.count = MagicMock(return_value=3)
    assert wait_until_count(loc, 3, timeout_ms=500) is True

def test_wait_until_count_never_matches():
    loc = MagicMock()
    loc.count = MagicMock(return_value=1)
    assert wait_until_count(loc, 3, timeout_ms=0) is False


def test_wait_for_url_contains_present():
    page = MagicMock()
    page.url = "https://blog.naver.com/write"
    assert wait_for_url_contains(page, "blog.naver.com") is True

def test_wait_for_url_contains_absent():
    page = MagicMock()
    page.url = "https://other.com"
    assert wait_for_url_contains(page, "blog.naver.com", timeout_ms=0) is False


# ===========================================================================
# Clicking — 계약: 클릭 여부, 실패 시 False
# ===========================================================================

def test_click_if_visible_clicks():
    loc = _loc(True)
    assert click_if_visible(loc) is True
    loc.click.assert_called_once()

def test_click_if_visible_not_visible():
    loc = _loc(False)
    assert click_if_visible(loc) is False
    loc.click.assert_not_called()

def test_click_if_visible_click_raises():
    loc = _loc(True)
    loc.click = MagicMock(side_effect=Exception())
    assert click_if_visible(loc) is False


def test_click_polling_success():
    loc = _loc(True)
    assert click_polling(loc, timeout_ms=500) is True

def test_click_polling_expired():
    assert click_polling(_loc(False), timeout_ms=0) is False


def test_click_nth_correct_index():
    loc = MagicMock()
    nth = _loc(True)
    loc.nth = MagicMock(return_value=nth)
    assert click_nth(loc, 2) is True
    loc.nth.assert_called_once_with(2)

def test_click_nth_not_visible():
    loc = MagicMock()
    loc.nth = MagicMock(return_value=_loc(False))
    assert click_nth(loc, 0) is False


# ===========================================================================
# Typing — 계약: 올바른 값 전달, 실패 시 False
# ===========================================================================

def test_fill_success():
    loc = _loc(True)
    assert fill(loc, "텍스트") is True
    loc.fill.assert_called_once_with("텍스트")

def test_fill_not_visible():
    assert fill(_loc(False), "text") is False

def test_fill_raises():
    loc = _loc(True)
    loc.fill = MagicMock(side_effect=Exception())
    assert fill(loc, "text") is False


def test_fill_and_submit_fills_and_enters():
    loc = _loc(True)
    fill_and_submit(loc, "검색어")
    loc.fill.assert_called_once_with("검색어")
    loc.press.assert_called_once_with("Enter")

def test_fill_and_submit_not_visible():
    assert fill_and_submit(_loc(False), "text") is False


def test_type_text_calls_keyboard():
    page = MagicMock()
    assert type_text(page, "hello") is True
    page.keyboard.type.assert_called_once_with("hello")

def test_type_text_raises():
    page = MagicMock()
    page.keyboard.type = MagicMock(side_effect=Exception())
    assert type_text(page, "text") is False


def test_clear_and_fill_sequence():
    loc = _loc(True)
    loc.page = MagicMock()
    clear_and_fill(loc, "new text")
    loc.click.assert_called_once()
    loc.page.keyboard.press.assert_called_once_with("Control+a")
    loc.page.keyboard.type.assert_called_once_with("new text")

def test_clear_and_fill_not_visible():
    assert clear_and_fill(_loc(False), "text") is False


def test_press_key_correct():
    loc = _loc(True)
    assert press_key(loc, "Enter") is True
    loc.press.assert_called_once_with("Enter")

def test_press_key_not_visible():
    assert press_key(_loc(False), "Tab") is False


def test_type_and_press_sequence():
    page = MagicMock()
    type_and_press(page, "검색어", "Enter")
    page.keyboard.type.assert_called_once_with("검색어")
    page.keyboard.press.assert_called_once_with("Enter")

def test_type_and_press_raises():
    page = MagicMock()
    page.keyboard.type = MagicMock(side_effect=Exception())
    assert type_and_press(page, "text", "Enter") is False


def test_select_option_by_value_correct():
    loc = _loc(True)
    select_option_by_value(loc, "opt1")
    loc.select_option.assert_called_once_with(value="opt1")

def test_select_option_by_value_not_visible():
    assert select_option_by_value(_loc(False), "opt1") is False


def test_hover_if_visible_hovers():
    loc = _loc(True)
    assert hover_if_visible(loc) is True
    loc.hover.assert_called_once()

def test_hover_if_visible_not_visible():
    assert hover_if_visible(_loc(False)) is False


# ===========================================================================
# State checks — 계약: 에러 시 안전한 기본값 반환
# ===========================================================================

def test_is_visible_true():
    loc = MagicMock()
    loc.is_visible = MagicMock(return_value=True)
    assert is_visible(loc) is True

def test_is_visible_error_returns_false():
    loc = MagicMock()
    loc.is_visible = MagicMock(side_effect=Exception())
    assert is_visible(loc) is False


def test_has_class_present():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="btn active")
    assert has_class(loc, "active") is True

def test_has_class_absent():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="btn")
    assert has_class(loc, "active") is False

def test_has_class_no_partial_match():
    """'se-is-selected' 클래스가 있을 때 'selected'로 매칭되면 안 됨."""
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="se-is-selected")
    assert has_class(loc, "selected") is False
    assert has_class(loc, "se-is-selected") is True


def test_get_count_returns_count():
    loc = MagicMock()
    loc.count = MagicMock(return_value=5)
    assert get_count(loc) == 5


# ===========================================================================
# Reading — 계약: strip, default 반환
# ===========================================================================

def test_get_text_strips():
    loc = MagicMock()
    loc.inner_text = MagicMock(return_value="  발행  ")
    assert get_text(loc) == "발행"

def test_get_text_default_on_error():
    loc = MagicMock()
    loc.inner_text = MagicMock(side_effect=Exception())
    assert get_text(loc, default="N/A") == "N/A"


def test_get_attribute_value():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="myclass")
    assert get_attribute(loc, "class") == "myclass"


def test_get_all_texts_strips():
    loc = MagicMock()
    loc.all_inner_texts = MagicMock(return_value=["  a  ", "b"])
    assert get_all_texts(loc) == ["a", "b"]


# ===========================================================================
# Scrolling / Upload
# ===========================================================================

def test_scroll_into_view_calls_method():
    loc = MagicMock()
    assert scroll_into_view(loc) is True
    loc.scroll_into_view_if_needed.assert_called_once()

def test_scroll_into_view_error():
    loc = MagicMock()
    loc.scroll_into_view_if_needed = MagicMock(side_effect=Exception())
    assert scroll_into_view(loc) is False


def test_upload_file_sets_path():
    page, trigger, fc = MagicMock(), MagicMock(), MagicMock()
    page.expect_file_chooser.return_value.__enter__ = MagicMock(return_value=fc)
    page.expect_file_chooser.return_value.__exit__  = MagicMock(return_value=False)
    assert upload_file(page, trigger, "/img.jpg") is True
    fc.value.set_files.assert_called_once_with("/img.jpg")

def test_upload_file_error():
    page, trigger = MagicMock(), MagicMock()
    page.expect_file_chooser = MagicMock(side_effect=Exception())
    assert upload_file(page, trigger, "img.jpg") is False


# ===========================================================================
# Composed: dismiss / dismiss_polling / dismiss_parallel
# ===========================================================================

def test_dismiss_clicks_and_waits_panel():
    loc, panel = _loc(True), _loc(True)
    assert dismiss(loc, panel_locator=panel) is True
    panel.wait_for.assert_called_once()

def test_dismiss_skips_panel_when_not_clicked():
    panel = _loc(True)
    assert dismiss(_loc(False), panel_locator=panel) is False
    panel.wait_for.assert_not_called()


def test_dismiss_polling_success():
    loc, panel = _loc(True), _loc(True)
    assert dismiss_polling(loc, panel_locator=panel, timeout_ms=500) is True
    panel.wait_for.assert_called_once()

def test_dismiss_polling_timeout():
    assert dismiss_polling(_loc(False), timeout_ms=0) is False


def test_dismiss_parallel_all_visible():
    locs = [_loc(True), _loc(True)]
    assert dismiss_parallel(locs, timeout_ms=500) == [True, True]
    for loc in locs:
        loc.click.assert_called_once()

def test_dismiss_parallel_skips_invisible():
    locs = [_loc(True), _loc(False)]
    dismiss_parallel(locs, timeout_ms=0)
    locs[1].click.assert_not_called()

def test_dismiss_parallel_empty():
    assert dismiss_parallel([], timeout_ms=500) == []


# ===========================================================================
# Parallel variants
# ===========================================================================

def test_wait_any_visible_first_match():
    locs = [_loc(False), _loc(True)]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=(loc.wait_for.side_effect is None))
    locs[0].is_visible = MagicMock(return_value=False)
    locs[1].is_visible = MagicMock(return_value=True)
    assert wait_any_visible(locs, timeout_ms=500) == 1

def test_wait_any_visible_none():
    locs = [MagicMock(), MagicMock()]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=False)
    assert wait_any_visible(locs, timeout_ms=0) == -1


def test_wait_all_visible_all():
    locs = [MagicMock(), MagicMock()]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=True)
    assert wait_all_visible(locs, timeout_ms=500) is True

def test_wait_all_visible_one_missing():
    locs = [MagicMock(), MagicMock()]
    locs[0].is_visible = MagicMock(return_value=True)
    locs[1].is_visible = MagicMock(return_value=False)
    assert wait_all_visible(locs, timeout_ms=0) is False


def test_any_visible_one_true():
    locs = [MagicMock(), MagicMock()]
    locs[0].is_visible = MagicMock(return_value=False)
    locs[1].is_visible = MagicMock(return_value=True)
    assert any_visible(locs) is True

def test_all_visible_one_false():
    locs = [MagicMock(), MagicMock()]
    locs[0].is_visible = MagicMock(return_value=True)
    locs[1].is_visible = MagicMock(return_value=False)
    assert all_visible(locs) is False


def test_click_parallel_all():
    locs = [_loc(True), _loc(True)]
    assert click_parallel(locs, timeout_ms=500) == [True, True]

def test_click_parallel_skips_invisible():
    locs = [_loc(True), _loc(False)]
    click_parallel(locs, timeout_ms=0)
    locs[1].click.assert_not_called()


def test_fill_parallel_fills_all():
    a, b = _loc(True), _loc(True)
    fill_parallel([(a, "hello"), (b, "world")], timeout_ms=500)
    a.fill.assert_called_once_with("hello")
    b.fill.assert_called_once_with("world")

def test_get_texts_parallel_strips():
    locs = [MagicMock(), MagicMock()]
    locs[0].inner_text = MagicMock(return_value="  제목  ")
    locs[1].inner_text = MagicMock(return_value="본문")
    assert get_texts_parallel(locs) == ["제목", "본문"]


def test_get_attributes_parallel_values():
    locs = [MagicMock(), MagicMock()]
    locs[0].get_attribute = MagicMock(return_value="primary")
    locs[1].get_attribute = MagicMock(return_value="secondary")
    assert get_attributes_parallel(locs, "class") == ["primary", "secondary"]


# ===========================================================================
# JavaScript
# ===========================================================================

def test_locator_dispatch_click_selected():
    loc = MagicMock()
    loc.nth.return_value.evaluate = MagicMock(return_value="selected")
    assert locator_dispatch_click(loc, index=0) == "selected"

def test_locator_dispatch_click_not_selected():
    loc = MagicMock()
    loc.nth.return_value.evaluate = MagicMock(return_value="not-selected")
    assert locator_dispatch_click(loc, index=1) == "not-selected"

def test_locator_dispatch_click_never_raises():
    loc = MagicMock()
    loc.nth = MagicMock(side_effect=Exception("crash"))
    result = locator_dispatch_click(loc, index=0)
    assert result.startswith("error:")


def test_js_dispatch_click_selected():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="selected")
    assert js_dispatch_click(js, "button.rep", 0) == "selected"

def test_js_dispatch_click_out_of_range():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="index 5 out of range (3 elements)")
    assert "out of range" in js_dispatch_click(js, "button", 5)


def test_js_evaluate_returns_result():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=42)
    assert js_evaluate(js, "() => 42") == 42

def test_js_evaluate_error_returns_none():
    js = MagicMock()
    js.evaluate = MagicMock(side_effect=Exception())
    assert js_evaluate(js, "() => boom()") is None


def test_js_scroll_into_view_success():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=True)
    assert js_scroll_into_view(js, "div.target") is True

def test_js_scroll_into_view_failure():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=False)
    assert js_scroll_into_view(js, "div.missing") is False


# ===========================================================================
# Frame resolution
# ===========================================================================

def test_find_editor_frame_finds_iframe():
    page, frame = MagicMock(), MagicMock()
    frame.first = frame
    frame.locator = MagicMock(return_value=_loc(True))
    page.frame_locator = MagicMock(return_value=frame)
    assert find_editor_frame(page, "#f", ".editor") == frame

def test_find_editor_frame_fallback_to_page():
    page, frame = MagicMock(), MagicMock()
    frame.first = frame
    frame.locator = MagicMock(return_value=_loc(False))
    page.frame_locator = MagicMock(return_value=frame)
    assert find_editor_frame(page, "#f", ".editor") == page

def test_find_js_frame_url_fragment():
    """url_fragment로 PostWriteForm frame을 정확히 찾는다."""
    page, main, blank, editor = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    main.url   = "https://blog.naver.com/id?Redirect=Write&"
    blank.url  = "about:blank"
    editor.url = "https://blog.naver.com/PostWriteForm.naver"
    page.main_frame = main
    page.frames     = [main, blank, editor]
    assert find_js_frame(page, url_fragment="PostWriteForm") == editor

def test_find_js_frame_url_fragment_stable_with_extra_frames():
    """input_buffer frame이 끼어도 url_fragment로 올바른 frame을 찾는다."""
    page, main, buf, editor = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    main.url   = "https://blog.naver.com/id"
    buf.url    = "about:blank"
    editor.url = "https://blog.naver.com/PostWriteForm.naver"
    page.main_frame = main
    page.frames     = [main, buf, editor]
    assert find_js_frame(page, url_fragment="PostWriteForm") == editor
