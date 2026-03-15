"""
tests/test_browser_actions.py
------------------------------
Layer 2: Browser Actions 단독 테스트

Playwright 없이 MagicMock만으로 실행.
각 함수의 성공 경로 + 실패 경로를 독립적으로 검증한다.
"""

import pytest
from unittest.mock import MagicMock, call, patch

from automator.browser_actions import (
    # Waiting
    wait_until_visible, wait_until_hidden, wait_until_attached,
    wait_until_count, wait_for_url_contains,
    # Clicking
    click_if_visible, click_polling, click_nth,
    # Typing
    fill, fill_and_submit, type_text, clear_and_fill, press_key, type_and_press,
    # Selection
    select_option_by_value, select_option_by_label,
    # Hovering
    hover_if_visible,
    # State checks
    is_visible, is_checked, is_disabled, is_editable, has_class, get_count,
    # Reading
    get_text, get_attribute, get_all_texts,
    # Scrolling
    scroll_into_view, scroll_to_bottom,
    # File upload
    upload_file,
    # Composed
    dismiss, dismiss_polling, dismiss_parallel,
    # Parallel
    wait_any_visible, wait_all_visible,
    any_visible, all_visible,
    click_parallel, fill_parallel,
    get_texts_parallel, get_attributes_parallel,
    # JavaScript
    js_dispatch_click, locator_dispatch_click,
    js_evaluate, js_scroll_into_view,
    # Frame
    find_editor_frame, find_js_frame,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _loc(visible: bool = True) -> MagicMock:
    """Locator that succeeds or times out based on visible flag."""
    loc = MagicMock()
    if visible:
        loc.wait_for = MagicMock()
    else:
        loc.wait_for = MagicMock(side_effect=Exception("timeout"))
    return loc


# ===========================================================================
# wait_until_visible
# ===========================================================================

@pytest.mark.unit
def test_wait_until_visible_returns_true():
    assert wait_until_visible(_loc(True)) is True


@pytest.mark.unit
def test_wait_until_visible_returns_false_on_timeout():
    assert wait_until_visible(_loc(False)) is False


@pytest.mark.unit
def test_wait_until_visible_never_raises():
    loc = MagicMock()
    loc.wait_for = MagicMock(side_effect=RuntimeError("crash"))
    assert wait_until_visible(loc) is False


# ===========================================================================
# wait_until_hidden
# ===========================================================================

@pytest.mark.unit
def test_wait_until_hidden_returns_true():
    assert wait_until_hidden(_loc(True)) is True


@pytest.mark.unit
def test_wait_until_hidden_returns_false_on_timeout():
    assert wait_until_hidden(_loc(False)) is False


@pytest.mark.unit
def test_wait_until_hidden_never_raises():
    loc = MagicMock()
    loc.wait_for = MagicMock(side_effect=RuntimeError("crash"))
    assert wait_until_hidden(loc) is False


# ===========================================================================
# wait_until_attached
# ===========================================================================

@pytest.mark.unit
def test_wait_until_attached_returns_true():
    assert wait_until_attached(_loc(True)) is True


@pytest.mark.unit
def test_wait_until_attached_returns_false_on_timeout():
    assert wait_until_attached(_loc(False)) is False


# ===========================================================================
# wait_until_count
# ===========================================================================

@pytest.mark.unit
def test_wait_until_count_returns_true_when_count_matches():
    loc = MagicMock()
    loc.count = MagicMock(return_value=3)
    assert wait_until_count(loc, 3, timeout_ms=500) is True


@pytest.mark.unit
def test_wait_until_count_returns_false_when_count_never_matches():
    loc = MagicMock()
    loc.count = MagicMock(return_value=1)
    assert wait_until_count(loc, 3, timeout_ms=0) is False


@pytest.mark.unit
def test_wait_until_count_returns_false_on_error():
    loc = MagicMock()
    loc.count = MagicMock(side_effect=Exception("error"))
    assert wait_until_count(loc, 1, timeout_ms=0) is False


# ===========================================================================
# wait_for_url_contains
# ===========================================================================

@pytest.mark.unit
def test_wait_for_url_contains_returns_true_when_fragment_present():
    page = MagicMock()
    page.url = "https://blog.naver.com/write"
    assert wait_for_url_contains(page, "blog.naver.com") is True


@pytest.mark.unit
def test_wait_for_url_contains_returns_false_when_fragment_absent():
    page = MagicMock()
    page.url = "https://other.com"
    assert wait_for_url_contains(page, "blog.naver.com", timeout_ms=0) is False


# ===========================================================================
# click_if_visible
# ===========================================================================

@pytest.mark.unit
def test_click_if_visible_clicks_and_returns_true():
    loc = _loc(True)
    assert click_if_visible(loc) is True
    loc.click.assert_called_once()


@pytest.mark.unit
def test_click_if_visible_returns_false_when_not_visible():
    loc = _loc(False)
    assert click_if_visible(loc) is False
    loc.click.assert_not_called()


@pytest.mark.unit
def test_click_if_visible_returns_false_when_click_raises():
    loc = _loc(True)
    loc.click = MagicMock(side_effect=Exception("click failed"))
    assert click_if_visible(loc) is False


# ===========================================================================
# click_polling
# ===========================================================================

@pytest.mark.unit
def test_click_polling_clicks_on_first_probe():
    loc = _loc(True)
    assert click_polling(loc, timeout_ms=500) is True
    loc.click.assert_called_once()


@pytest.mark.unit
def test_click_polling_returns_false_at_zero_timeout():
    loc = _loc(False)
    assert click_polling(loc, timeout_ms=0) is False


# ===========================================================================
# click_nth
# ===========================================================================

@pytest.mark.unit
def test_click_nth_clicks_correct_element():
    loc = MagicMock()
    nth = _loc(True)
    loc.nth = MagicMock(return_value=nth)
    assert click_nth(loc, 2) is True
    loc.nth.assert_called_once_with(2)
    nth.click.assert_called_once()


@pytest.mark.unit
def test_click_nth_returns_false_when_not_visible():
    loc = MagicMock()
    nth = _loc(False)
    loc.nth = MagicMock(return_value=nth)
    assert click_nth(loc, 0) is False


# ===========================================================================
# fill
# ===========================================================================

@pytest.mark.unit
def test_fill_fills_text():
    loc = _loc(True)
    assert fill(loc, "테스트") is True
    loc.fill.assert_called_once_with("테스트")


@pytest.mark.unit
def test_fill_returns_false_when_not_visible():
    assert fill(_loc(False), "text") is False


@pytest.mark.unit
def test_fill_returns_false_when_fill_raises():
    loc = _loc(True)
    loc.fill = MagicMock(side_effect=Exception("readonly"))
    assert fill(loc, "text") is False


# ===========================================================================
# fill_and_submit
# ===========================================================================

@pytest.mark.unit
def test_fill_and_submit_fills_and_presses_enter():
    loc = _loc(True)
    assert fill_and_submit(loc, "검색어") is True
    loc.fill.assert_called_once_with("검색어")
    loc.press.assert_called_once_with("Enter")


@pytest.mark.unit
def test_fill_and_submit_returns_false_when_not_visible():
    assert fill_and_submit(_loc(False), "text") is False


# ===========================================================================
# type_text
# ===========================================================================

@pytest.mark.unit
def test_type_text_calls_keyboard_type():
    page = MagicMock()
    assert type_text(page, "hello") is True
    page.keyboard.type.assert_called_once_with("hello")


@pytest.mark.unit
def test_type_text_returns_false_on_error():
    page = MagicMock()
    page.keyboard.type = MagicMock(side_effect=Exception())
    assert type_text(page, "text") is False


# ===========================================================================
# clear_and_fill
# ===========================================================================

@pytest.mark.unit
def test_clear_and_fill_selects_all_and_types():
    loc = _loc(True)
    loc.page = MagicMock()
    assert clear_and_fill(loc, "new text") is True
    loc.click.assert_called_once()
    loc.page.keyboard.press.assert_called_once_with("Control+a")
    loc.page.keyboard.type.assert_called_once_with("new text")


@pytest.mark.unit
def test_clear_and_fill_returns_false_on_error():
    loc = _loc(False)
    assert clear_and_fill(loc, "text") is False


# ===========================================================================
# press_key
# ===========================================================================

@pytest.mark.unit
def test_press_key_presses_correct_key():
    loc = _loc(True)
    assert press_key(loc, "Enter") is True
    loc.press.assert_called_once_with("Enter")


@pytest.mark.unit
def test_press_key_returns_false_when_not_visible():
    assert press_key(_loc(False), "Tab") is False


# ===========================================================================
# type_and_press
# ===========================================================================

@pytest.mark.unit
def test_type_and_press_types_then_presses():
    page = MagicMock()
    assert type_and_press(page, "검색어", "Enter") is True
    page.keyboard.type.assert_called_once_with("검색어")
    page.keyboard.press.assert_called_once_with("Enter")


@pytest.mark.unit
def test_type_and_press_returns_false_on_error():
    page = MagicMock()
    page.keyboard.type = MagicMock(side_effect=Exception())
    assert type_and_press(page, "text", "Enter") is False


# ===========================================================================
# select_option_by_value
# ===========================================================================

@pytest.mark.unit
def test_select_option_by_value_selects_correct_value():
    loc = _loc(True)
    assert select_option_by_value(loc, "opt1") is True
    loc.select_option.assert_called_once_with(value="opt1")


@pytest.mark.unit
def test_select_option_by_value_returns_false_when_not_visible():
    assert select_option_by_value(_loc(False), "opt1") is False


# ===========================================================================
# select_option_by_label
# ===========================================================================

@pytest.mark.unit
def test_select_option_by_label_selects_correct_label():
    loc = _loc(True)
    assert select_option_by_label(loc, "선택지 1") is True
    loc.select_option.assert_called_once_with(label="선택지 1")


# ===========================================================================
# hover_if_visible
# ===========================================================================

@pytest.mark.unit
def test_hover_if_visible_hovers():
    loc = _loc(True)
    assert hover_if_visible(loc) is True
    loc.hover.assert_called_once()


@pytest.mark.unit
def test_hover_if_visible_returns_false_when_not_visible():
    assert hover_if_visible(_loc(False)) is False


# ===========================================================================
# State checks
# ===========================================================================

@pytest.mark.unit
def test_is_visible_returns_true():
    loc = MagicMock()
    loc.is_visible = MagicMock(return_value=True)
    assert is_visible(loc) is True


@pytest.mark.unit
def test_is_visible_returns_false_on_error():
    loc = MagicMock()
    loc.is_visible = MagicMock(side_effect=Exception())
    assert is_visible(loc) is False


@pytest.mark.unit
def test_is_checked_returns_true():
    loc = MagicMock()
    loc.is_checked = MagicMock(return_value=True)
    assert is_checked(loc) is True


@pytest.mark.unit
def test_is_checked_returns_false_on_error():
    loc = MagicMock()
    loc.is_checked = MagicMock(side_effect=Exception())
    assert is_checked(loc) is False


@pytest.mark.unit
def test_is_disabled_returns_false_when_enabled():
    loc = MagicMock()
    loc.is_disabled = MagicMock(return_value=False)
    assert is_disabled(loc) is False


@pytest.mark.unit
def test_is_disabled_returns_true_on_error():
    loc = MagicMock()
    loc.is_disabled = MagicMock(side_effect=Exception())
    assert is_disabled(loc) is True  # safe default


@pytest.mark.unit
def test_is_editable_returns_true():
    loc = MagicMock()
    loc.is_editable = MagicMock(return_value=True)
    assert is_editable(loc) is True


@pytest.mark.unit
def test_has_class_returns_true_when_class_present():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="btn btn-primary active")
    assert has_class(loc, "active") is True


@pytest.mark.unit
def test_has_class_returns_false_when_class_absent():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="btn btn-primary")
    assert has_class(loc, "active") is False


@pytest.mark.unit
def test_has_class_no_partial_match():
    """'se-is-selected'이 있을 때 'selected'만으로 True가 되면 안 됨."""
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="se-is-selected")
    assert has_class(loc, "selected") is False
    assert has_class(loc, "se-is-selected") is True


@pytest.mark.unit
def test_get_count_returns_count():
    loc = MagicMock()
    loc.count = MagicMock(return_value=5)
    assert get_count(loc) == 5


@pytest.mark.unit
def test_get_count_returns_zero_on_error():
    loc = MagicMock()
    loc.count = MagicMock(side_effect=Exception())
    assert get_count(loc) == 0


# ===========================================================================
# Reading
# ===========================================================================

@pytest.mark.unit
def test_get_text_returns_stripped_text():
    loc = MagicMock()
    loc.inner_text = MagicMock(return_value="  발행  ")
    assert get_text(loc) == "발행"


@pytest.mark.unit
def test_get_text_returns_default_on_error():
    loc = MagicMock()
    loc.inner_text = MagicMock(side_effect=Exception())
    assert get_text(loc, default="N/A") == "N/A"


@pytest.mark.unit
def test_get_attribute_returns_value():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value="myclass")
    assert get_attribute(loc, "class") == "myclass"


@pytest.mark.unit
def test_get_attribute_returns_default_when_absent():
    loc = MagicMock()
    loc.get_attribute = MagicMock(return_value=None)
    assert get_attribute(loc, "data-x", default="fallback") == "fallback"


@pytest.mark.unit
def test_get_all_texts_returns_list():
    loc = MagicMock()
    loc.all_inner_texts = MagicMock(return_value=["  a  ", "b", "  c"])
    assert get_all_texts(loc) == ["a", "b", "c"]


@pytest.mark.unit
def test_get_all_texts_returns_empty_on_error():
    loc = MagicMock()
    loc.all_inner_texts = MagicMock(side_effect=Exception())
    assert get_all_texts(loc) == []


# ===========================================================================
# Scrolling
# ===========================================================================

@pytest.mark.unit
def test_scroll_into_view_returns_true():
    loc = MagicMock()
    assert scroll_into_view(loc) is True
    loc.scroll_into_view_if_needed.assert_called_once()


@pytest.mark.unit
def test_scroll_into_view_returns_false_on_error():
    loc = MagicMock()
    loc.scroll_into_view_if_needed = MagicMock(side_effect=Exception())
    assert scroll_into_view(loc) is False


@pytest.mark.unit
def test_scroll_to_bottom_evaluates_js():
    page = MagicMock()
    assert scroll_to_bottom(page) is True
    page.evaluate.assert_called_once()


@pytest.mark.unit
def test_scroll_to_bottom_returns_false_on_error():
    page = MagicMock()
    page.evaluate = MagicMock(side_effect=Exception())
    assert scroll_to_bottom(page) is False


# ===========================================================================
# File upload
# ===========================================================================

@pytest.mark.unit
def test_upload_file_sets_correct_path():
    page    = MagicMock()
    trigger = MagicMock()
    fc      = MagicMock()
    page.expect_file_chooser.return_value.__enter__ = MagicMock(return_value=fc)
    page.expect_file_chooser.return_value.__exit__  = MagicMock(return_value=False)
    assert upload_file(page, trigger, "/path/to/img.jpg") is True
    fc.value.set_files.assert_called_once_with("/path/to/img.jpg")


@pytest.mark.unit
def test_upload_file_returns_false_on_error():
    page    = MagicMock()
    trigger = MagicMock()
    page.expect_file_chooser = MagicMock(side_effect=Exception("no chooser"))
    assert upload_file(page, trigger, "img.jpg") is False


# ===========================================================================
# dismiss / dismiss_polling
# ===========================================================================

@pytest.mark.unit
def test_dismiss_clicks_and_waits_for_panel():
    loc   = _loc(True)
    panel = _loc(True)
    assert dismiss(loc, panel_locator=panel) is True
    panel.wait_for.assert_called_once()


@pytest.mark.unit
def test_dismiss_skips_panel_when_not_clicked():
    panel = _loc(True)
    assert dismiss(_loc(False), panel_locator=panel) is False
    panel.wait_for.assert_not_called()


@pytest.mark.unit
def test_dismiss_without_panel_does_not_raise():
    assert dismiss(_loc(True), panel_locator=None) is True


@pytest.mark.unit
def test_dismiss_polling_clicks_and_waits():
    loc   = _loc(True)
    panel = _loc(True)
    assert dismiss_polling(loc, panel_locator=panel, timeout_ms=500) is True
    panel.wait_for.assert_called_once()


@pytest.mark.unit
def test_dismiss_polling_returns_false_on_timeout():
    assert dismiss_polling(_loc(False), timeout_ms=0) is False


# ===========================================================================
# dismiss_parallel
# ===========================================================================

@pytest.mark.unit
def test_dismiss_parallel_clicks_all_visible():
    locs = [_loc(True), _loc(True), _loc(True)]
    results = dismiss_parallel(locs, timeout_ms=500)
    assert results == [True, True, True]
    for loc in locs:
        loc.click.assert_called_once()


@pytest.mark.unit
def test_dismiss_parallel_skips_invisible():
    locs = [_loc(True), _loc(False), _loc(True)]
    results = dismiss_parallel(locs, timeout_ms=0)
    # invisible one is not clicked
    locs[1].click.assert_not_called()


@pytest.mark.unit
def test_dismiss_parallel_returns_false_for_each_invisible():
    locs = [_loc(False), _loc(False)]
    results = dismiss_parallel(locs, timeout_ms=0)
    assert results == [False, False]


@pytest.mark.unit
def test_dismiss_parallel_empty_list_returns_empty():
    assert dismiss_parallel([], timeout_ms=1_000) == []


@pytest.mark.unit
def test_dismiss_parallel_shared_timeout():
    """단일 타임아웃 안에서 모두 처리 — 타임아웃이 N배가 되지 않음."""
    import time
    locs = [_loc(False), _loc(False)]
    start = time.monotonic()
    dismiss_parallel(locs, timeout_ms=200)
    elapsed_ms = (time.monotonic() - start) * 1_000
    # 200ms 타임아웃 × 2개 = 400ms 가 아니라 ~200ms 이어야 함
    assert elapsed_ms < 400, f"timeout multiplied: {elapsed_ms:.0f}ms"


# ===========================================================================
# js_dispatch_click
# ===========================================================================

@pytest.mark.unit
def test_js_dispatch_click_returns_selected():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="selected")
    assert js_dispatch_click(js, "button.rep", 0) == "selected"


@pytest.mark.unit
def test_js_dispatch_click_passes_correct_args():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="selected")
    js_dispatch_click(js, "button.my", 2)
    assert js.evaluate.call_args[0][1] == ["button.my", 2]


@pytest.mark.unit
def test_js_dispatch_click_out_of_range():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="index 5 out of range (3 elements)")
    assert "out of range" in js_dispatch_click(js, "button", 5)


# ===========================================================================
# locator_dispatch_click
# ===========================================================================

@pytest.mark.unit
def test_locator_dispatch_click_returns_selected():
    loc = MagicMock()
    nth = MagicMock()
    nth.evaluate = MagicMock(return_value="selected")
    loc.nth = MagicMock(return_value=nth)
    assert locator_dispatch_click(loc, index=0) == "selected"
    loc.nth.assert_called_once_with(0)


@pytest.mark.unit
def test_locator_dispatch_click_returns_not_selected():
    loc = MagicMock()
    nth = MagicMock()
    nth.evaluate = MagicMock(return_value="not-selected")
    loc.nth = MagicMock(return_value=nth)
    assert locator_dispatch_click(loc, index=1) == "not-selected"


@pytest.mark.unit
def test_locator_dispatch_click_returns_error_on_exception():
    loc = MagicMock()
    nth = MagicMock()
    nth.evaluate = MagicMock(side_effect=Exception("shadow DOM error"))
    loc.nth = MagicMock(return_value=nth)
    result = locator_dispatch_click(loc, index=0)
    assert result.startswith("error:")


@pytest.mark.unit
def test_locator_dispatch_click_never_raises():
    loc = MagicMock()
    loc.nth = MagicMock(side_effect=Exception("crash"))
    result = locator_dispatch_click(loc, index=0)
    assert result.startswith("error:")


# ===========================================================================
# js_evaluate
# ===========================================================================

@pytest.mark.unit
def test_js_evaluate_returns_result():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=42)
    assert js_evaluate(js, "() => 42") == 42


@pytest.mark.unit
def test_js_evaluate_passes_arg():
    js = MagicMock()
    js.evaluate = MagicMock(return_value="h1")
    js_evaluate(js, "(sel) => sel", "h1")
    assert js.evaluate.call_args[0][1] == "h1"


@pytest.mark.unit
def test_js_evaluate_returns_none_on_error():
    js = MagicMock()
    js.evaluate = MagicMock(side_effect=Exception("JS error"))
    assert js_evaluate(js, "() => boom()") is None


# ===========================================================================
# js_scroll_into_view
# ===========================================================================

@pytest.mark.unit
def test_js_scroll_into_view_returns_true_on_success():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=True)
    assert js_scroll_into_view(js, "div.target", 0) is True


@pytest.mark.unit
def test_js_scroll_into_view_returns_false_on_failure():
    js = MagicMock()
    js.evaluate = MagicMock(return_value=False)
    assert js_scroll_into_view(js, "div.missing", 99) is False


# ===========================================================================
# find_editor_frame
# ===========================================================================

@pytest.mark.unit
def test_find_editor_frame_returns_iframe_when_found():
    page  = MagicMock()
    frame = MagicMock()
    loc   = _loc(True)
    frame.first   = frame
    frame.locator = MagicMock(return_value=loc)
    page.frame_locator = MagicMock(return_value=frame)
    assert find_editor_frame(page, "#f", ".editor") == frame


@pytest.mark.unit
def test_find_editor_frame_falls_back_to_page():
    page  = MagicMock()
    frame = MagicMock()
    loc   = _loc(False)
    frame.first   = frame
    frame.locator = MagicMock(return_value=loc)
    page.frame_locator = MagicMock(return_value=frame)
    assert find_editor_frame(page, "#f", ".editor") == page


# ===========================================================================
# find_js_frame
# ===========================================================================

@pytest.mark.unit
def test_find_js_frame_returns_sub_frame():
    page = MagicMock()
    main, sub = MagicMock(), MagicMock()
    page.main_frame = main
    page.frames     = [main, sub]
    assert find_js_frame(page) == sub


@pytest.mark.unit
def test_find_js_frame_falls_back_to_main():
    page = MagicMock()
    main = MagicMock()
    page.main_frame = main
    page.frames     = [main]
    assert find_js_frame(page) == main


@pytest.mark.unit
def test_find_js_frame_url_fragment_pinpoints_correct_frame():
    """url_fragment가 주어지면 URL이 일치하는 frame을 반환한다."""
    page   = MagicMock()
    main   = MagicMock()
    blank  = MagicMock()
    editor = MagicMock()
    main.url   = "https://blog.naver.com/id?Redirect=Write&"
    blank.url  = "about:blank"
    editor.url = "https://blog.naver.com/PostWriteForm.naver?blogId=id"
    page.main_frame = main
    page.frames     = [main, editor, blank]
    assert find_js_frame(page, url_fragment="PostWriteForm") == editor


@pytest.mark.unit
def test_find_js_frame_url_fragment_falls_back_when_no_match():
    """url_fragment 일치 frame이 없으면 첫 번째 sub-frame으로 fallback."""
    page  = MagicMock()
    main  = MagicMock()
    sub   = MagicMock()
    main.url = "https://example.com"
    sub.url  = "about:blank"
    page.main_frame = main
    page.frames     = [main, sub]
    assert find_js_frame(page, url_fragment="PostWriteForm") == sub


@pytest.mark.unit
def test_find_js_frame_stable_after_new_frames_added():
    """input_buffer 같은 frame이 추가돼도 url_fragment로 올바른 frame을 반환한다."""
    page        = MagicMock()
    main        = MagicMock()
    editor      = MagicMock()
    input_buf   = MagicMock()
    main.url      = "https://blog.naver.com/id"
    editor.url    = "https://blog.naver.com/PostWriteForm.naver"
    input_buf.url = "about:blank"
    page.main_frame = main
    # input_buffer가 첫 번째 sub-frame이 되는 상황
    page.frames     = [main, input_buf, editor]
    result = find_js_frame(page, url_fragment="PostWriteForm")
    assert result == editor, "input_buffer가 끼어도 editor frame을 찾아야 한다"

# ===========================================================================
# Parallel variants
# ===========================================================================

# --- wait_any_visible -------------------------------------------------------

@pytest.mark.unit
def test_wait_any_visible_returns_index_of_first_visible():
    locs = [_loc(False), _loc(True), _loc(True)]
    assert wait_any_visible(locs, timeout_ms=500) == 1


@pytest.mark.unit
def test_wait_any_visible_returns_minus_one_when_none():
    locs = [_loc(False), _loc(False)]
    assert wait_any_visible(locs, timeout_ms=0) == -1


@pytest.mark.unit
def test_wait_any_visible_returns_zero_for_first():
    locs = [_loc(True), _loc(True)]
    assert wait_any_visible(locs, timeout_ms=500) == 0


# --- wait_all_visible -------------------------------------------------------

@pytest.mark.unit
def test_wait_all_visible_returns_true_when_all_visible():
    locs = [_loc(True), _loc(True), _loc(True)]
    assert wait_all_visible(locs, timeout_ms=500) is True


@pytest.mark.unit
def test_wait_all_visible_returns_false_when_one_missing():
    locs = [_loc(True), _loc(False)]
    assert wait_all_visible(locs, timeout_ms=0) is False


@pytest.mark.unit
def test_wait_all_visible_returns_false_for_empty():
    assert wait_all_visible([], timeout_ms=500) is False


# --- any_visible / all_visible ----------------------------------------------

@pytest.mark.unit
def test_any_visible_returns_true_when_one_is_visible():
    locs = [_loc(False), _loc(True)]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=loc.wait_for.side_effect is None)
    locs[0].is_visible = MagicMock(return_value=False)
    locs[1].is_visible = MagicMock(return_value=True)
    assert any_visible(locs) is True


@pytest.mark.unit
def test_any_visible_returns_false_when_none_visible():
    locs = [MagicMock(), MagicMock()]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=False)
    assert any_visible(locs) is False


@pytest.mark.unit
def test_all_visible_returns_true_when_all_visible():
    locs = [MagicMock(), MagicMock()]
    for loc in locs:
        loc.is_visible = MagicMock(return_value=True)
    assert all_visible(locs) is True


@pytest.mark.unit
def test_all_visible_returns_false_when_one_invisible():
    locs = [MagicMock(), MagicMock()]
    locs[0].is_visible = MagicMock(return_value=True)
    locs[1].is_visible = MagicMock(return_value=False)
    assert all_visible(locs) is False


@pytest.mark.unit
def test_all_visible_returns_false_for_empty():
    assert all_visible([]) is False


# --- click_parallel ---------------------------------------------------------

@pytest.mark.unit
def test_click_parallel_clicks_all_visible():
    locs = [_loc(True), _loc(True)]
    results = click_parallel(locs, timeout_ms=500)
    assert results == [True, True]
    for loc in locs:
        loc.click.assert_called_once()


@pytest.mark.unit
def test_click_parallel_skips_invisible():
    locs = [_loc(True), _loc(False), _loc(True)]
    results = click_parallel(locs, timeout_ms=0)
    locs[1].click.assert_not_called()


@pytest.mark.unit
def test_click_parallel_returns_false_for_invisible():
    locs = [_loc(False), _loc(False)]
    assert click_parallel(locs, timeout_ms=0) == [False, False]


@pytest.mark.unit
def test_click_parallel_shared_timeout():
    """타임아웃이 N배가 되지 않는다."""
    import time
    locs = [_loc(False), _loc(False), _loc(False)]
    start = time.monotonic()
    click_parallel(locs, timeout_ms=200)
    elapsed_ms = (time.monotonic() - start) * 1_000
    assert elapsed_ms < 600, f"timeout multiplied: {elapsed_ms:.0f}ms"


# --- fill_parallel ----------------------------------------------------------

@pytest.mark.unit
def test_fill_parallel_fills_all_fields():
    loc_a, loc_b = _loc(True), _loc(True)
    results = fill_parallel([(loc_a, "hello"), (loc_b, "world")], timeout_ms=500)
    assert results == [True, True]
    loc_a.fill.assert_called_once_with("hello")
    loc_b.fill.assert_called_once_with("world")


@pytest.mark.unit
def test_fill_parallel_skips_invisible_field():
    loc_a, loc_b = _loc(True), _loc(False)
    results = fill_parallel([(loc_a, "ok"), (loc_b, "skip")], timeout_ms=0)
    loc_b.fill.assert_not_called()
    assert results[0] is True
    assert results[1] is False


@pytest.mark.unit
def test_fill_parallel_returns_false_when_fill_raises():
    loc = _loc(True)
    loc.fill = MagicMock(side_effect=Exception("readonly"))
    results = fill_parallel([(loc, "text")], timeout_ms=500)
    assert results == [False]


# --- get_texts_parallel -----------------------------------------------------

@pytest.mark.unit
def test_get_texts_parallel_returns_all_texts():
    locs = [MagicMock(), MagicMock()]
    locs[0].inner_text = MagicMock(return_value="  제목  ")
    locs[1].inner_text = MagicMock(return_value="본문")
    assert get_texts_parallel(locs) == ["제목", "본문"]


@pytest.mark.unit
def test_get_texts_parallel_uses_default_on_error():
    locs = [MagicMock(), MagicMock()]
    locs[0].inner_text = MagicMock(return_value="ok")
    locs[1].inner_text = MagicMock(side_effect=Exception())
    assert get_texts_parallel(locs, default="N/A") == ["ok", "N/A"]


@pytest.mark.unit
def test_get_texts_parallel_empty_list():
    assert get_texts_parallel([]) == []


# --- get_attributes_parallel ------------------------------------------------

@pytest.mark.unit
def test_get_attributes_parallel_returns_values():
    locs = [MagicMock(), MagicMock()]
    locs[0].get_attribute = MagicMock(return_value="btn-primary")
    locs[1].get_attribute = MagicMock(return_value="btn-secondary")
    result = get_attributes_parallel(locs, "class")
    assert result == ["btn-primary", "btn-secondary"]
    for loc in locs:
        loc.get_attribute.assert_called_once_with("class")


@pytest.mark.unit
def test_get_attributes_parallel_uses_default_on_none():
    locs = [MagicMock()]
    locs[0].get_attribute = MagicMock(return_value=None)
    assert get_attributes_parallel(locs, "href", default="#") == ["#"]


@pytest.mark.unit
def test_get_attributes_parallel_uses_default_on_error():
    locs = [MagicMock()]
    locs[0].get_attribute = MagicMock(side_effect=Exception())
    assert get_attributes_parallel(locs, "class", default="") == [""]


@pytest.mark.unit
def test_get_attributes_parallel_empty_list():
    assert get_attributes_parallel([], "class") == []
