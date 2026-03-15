"""
tests/test_editor_unit.py
--------------------------
Layer 3: SmartEditorOne (Editor Shell) 테스트

SmartEditorOne이 BlogEditor ABC를 올바르게 구현하는지,
그리고 _wait_for_editor_ready의 stability window가 올바르게 동작하는지 검증한다.
"""

import pytest
from unittest.mock import MagicMock, call, patch

from automator.smart_editor import SmartEditorOne


# ===========================================================================
# Fixtures
# ===========================================================================

def _make_locator() -> MagicMock:
    loc       = MagicMock()
    loc.first = loc
    loc.last  = loc
    loc.nth   = MagicMock(return_value=loc)
    return loc


def _make_page() -> MagicMock:
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


@pytest.mark.unit
def test_open_calls_wait_for_editor_ready(mock_page):
    """open()은 _wait_for_editor_ready를 반드시 호출한다."""
    calls = []

    def fake(self, frame, sel, **kwargs):
        calls.append(True)

    with patch.object(SmartEditorOne, "_wait_for_editor_ready", fake):
        SmartEditorOne(mock_page, WRITE_URL).open()

    assert calls, "_wait_for_editor_ready must be called"


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
    """set_representative_image는 block을 hover한 후 locator.evaluate로 클릭한다."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.nth.return_value.evaluate = MagicMock(return_value="selected")
    SmartEditorOne(mock_page, WRITE_URL).set_representative_image(0)
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
# 8. _wait_for_editor_ready() — stability window
# ===========================================================================

@pytest.mark.unit
def test_wait_for_editor_ready_returns_after_clean_streak(mock_page):
    """오버레이가 없는 사이클이 stable_streak번 연속되면 리턴한다."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.first      = loc
    loc.is_visible = MagicMock(return_value=True)

    with patch("automator.smart_editor.click_if_visible", return_value=False):
        with patch("automator.smart_editor.time") as mock_time:
            mock_time.monotonic = MagicMock(return_value=0)
            mock_time.sleep     = MagicMock()
            SmartEditorOne(mock_page, WRITE_URL)._wait_for_editor_ready(
                frame, MagicMock(),
                timeout_ms=20_000, stable_streak=3, probe_ms=400,
            )
    # 예외 없이 리턴했으면 성공


@pytest.mark.unit
def test_wait_for_editor_ready_resets_streak_on_click(mock_page):
    """오버레이를 클릭한 사이클에서는 streak이 0으로 리셋된다."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.first      = loc
    loc.is_visible = MagicMock(return_value=True)

    click_log = []
    # 처음 4번 클릭(2 오버레이 × 2 사이클), 이후 clean
    results = [True, True, True, True] + [False] * 20
    idx     = [0]

    def fake_click(locator, timeout_ms=300):
        r = results[min(idx[0], len(results) - 1)]
        idx[0] += 1
        click_log.append(r)
        return r

    with patch("automator.smart_editor.click_if_visible", fake_click):
        with patch("automator.smart_editor.time") as mock_time:
            mock_time.monotonic = MagicMock(return_value=0)
            mock_time.sleep     = MagicMock()
            SmartEditorOne(mock_page, WRITE_URL)._wait_for_editor_ready(
                frame, MagicMock(),
                timeout_ms=20_000, stable_streak=3, probe_ms=300,
            )

    assert any(click_log), "overlay click must have occurred"
    assert len(click_log) > 4, "probing must continue after streak reset"


@pytest.mark.unit
def test_wait_for_editor_ready_checks_all_overlays_per_cycle(mock_page):
    """한 사이클에서 모든 오버레이를 확인한다 (any() 단락 없음)."""
    frame = mock_page.frame_locator.return_value.first
    loc   = frame.locator.return_value
    loc.first      = loc
    loc.is_visible = MagicMock(return_value=True)

    call_count = [0]

    def fake_click(locator, timeout_ms=300):
        call_count[0] += 1
        # 처음 2번만 True(한 사이클 내 두 오버레이), 이후 clean
        return call_count[0] <= 2

    with patch("automator.smart_editor.click_if_visible", fake_click):
        with patch("automator.smart_editor.time") as mock_time:
            mock_time.monotonic = MagicMock(return_value=0)
            mock_time.sleep     = MagicMock()
            SmartEditorOne(mock_page, WRITE_URL)._wait_for_editor_ready(
                frame, MagicMock(),
                timeout_ms=20_000, stable_streak=3, probe_ms=300,
            )

    # 첫 사이클에서 2개 오버레이 모두 체크됨 (short-circuit 없음)
    assert call_count[0] >= 2, "both overlays must be checked in the same cycle"


# ===========================================================================
# 9. publish() — schedule_at propagation into Naver reservation UI
# ===========================================================================

from datetime import datetime, timedelta, timezone
from automator.options import KST


def _make_schedule_page() -> MagicMock:
    """
    _make_page()에 select_option 지원을 추가한 버전.
    publish_scheduled / publish_scheduled_hour / publish_scheduled_min
    locator 모두 동일한 mock locator를 반환한다.
    """
    page = _make_page()
    loc  = _make_locator()
    page.locator       = MagicMock(return_value=loc)
    page.get_by_role   = MagicMock(return_value=loc)
    page.get_by_label  = MagicMock(return_value=loc)
    frame = page.frame_locator.return_value.first
    frame.locator      = MagicMock(return_value=loc)
    frame.get_by_role  = MagicMock(return_value=loc)
    frame.get_by_label = MagicMock(return_value=loc)
    return page, loc


@pytest.mark.unit
def test_round_minute_to_10_floors_to_nearest_ten():
    """_round_minute_to_10 is a floor-to-10 operation."""
    from automator.smart_editor import SmartEditorOne
    r = SmartEditorOne._round_minute_to_10
    assert r(0)  == "00"
    assert r(9)  == "00"
    assert r(10) == "10"
    assert r(15) == "10"
    assert r(37) == "30"
    assert r(40) == "40"
    assert r(55) == "50"
    assert r(59) == "50"


@pytest.mark.unit
def test_publish_dry_run_with_schedule_at_does_not_click(mock_page):
    """dry_run=True이면 schedule_at이 있어도 클릭 없이 종료한다."""
    target = datetime.now(tz=KST) + timedelta(hours=2)
    SmartEditorOne(mock_page, WRITE_URL, dry_run=True).publish(schedule_at=target)
    mock_page.get_by_role.return_value.click.assert_not_called()
    mock_page.locator.return_value.click.assert_not_called()


@pytest.mark.unit
def test_publish_with_schedule_at_calls_set_scheduled(mock_page):
    """
    schedule_at이 주어지면 publish()가 _set_scheduled_publish()를 호출해야 한다.
    """
    target = datetime.now(tz=KST) + timedelta(hours=2)
    editor = SmartEditorOne(mock_page, WRITE_URL, dry_run=False)
    called = []
    editor._set_scheduled_publish = lambda dt: called.append(dt)
    editor.publish(schedule_at=target)
    assert called == [target], "_set_scheduled_publish must be called with schedule_at"


@pytest.mark.unit
def test_publish_without_schedule_at_skips_set_scheduled(mock_page):
    """
    schedule_at=None이면 _set_scheduled_publish()를 호출하지 않는다.
    """
    editor = SmartEditorOne(mock_page, WRITE_URL, dry_run=False)
    called = []
    editor._set_scheduled_publish = lambda dt: called.append(dt)
    editor.publish(schedule_at=None)
    assert called == [], "_set_scheduled_publish must NOT be called for immediate publish"


@pytest.mark.unit
def test_set_scheduled_publish_selects_hour_and_minute(mock_page):
    """
    _set_scheduled_publish()가 예약 라디오 클릭 → 시 선택 → 분 선택을 수행한다.
    select_option이 hour와 rounded minute으로 호출됐는지 검증한다.
    """
    # target: 16시 37분 → hour="16", minute="30" (floor)
    target = datetime(2026, 3, 15, 16, 37, tzinfo=KST)
    editor = SmartEditorOne(mock_page, WRITE_URL, dry_run=False)

    hour_calls   = []
    minute_calls = []

    def fake_select_hour(locator, value, timeout_ms=5_000):
        hour_calls.append(value)
        return True

    def fake_select_minute(locator, value, timeout_ms=5_000):
        minute_calls.append(value)
        return True

    with patch("automator.smart_editor.click_if_visible",   return_value=True), \
         patch("automator.smart_editor.select_option_by_value",
               side_effect=[True, True, True]):
        # Patch select directly on the module to capture arguments
        import automator.smart_editor as sm_mod
        original = sm_mod.select_option_by_value
        calls = []
        def capturing_select(locator, value, timeout_ms=5_000):
            calls.append(value)
            return True
        sm_mod.select_option_by_value = capturing_select
        try:
            editor._set_scheduled_publish(target)
        finally:
            sm_mod.select_option_by_value = original

    assert "16" in calls,  f"hour '16' must be selected, got {calls}"
    assert "30" in calls,  f"minute '30' must be selected (floor of 37), got {calls}"


@pytest.mark.unit
def test_set_scheduled_publish_rounds_minute_55_to_50(mock_page):
    """55분은 50으로 내림된다 (분 드롭다운은 10분 단위)."""
    target = datetime(2026, 3, 15, 9, 55, tzinfo=KST)
    editor = SmartEditorOne(mock_page, WRITE_URL, dry_run=False)

    import automator.smart_editor as sm_mod
    calls = []
    original = sm_mod.select_option_by_value
    def capturing_select(locator, value, timeout_ms=5_000):
        calls.append(value)
        return True
    sm_mod.select_option_by_value = capturing_select
    try:
        with patch("automator.smart_editor.click_if_visible", return_value=True):
            editor._set_scheduled_publish(target)
    finally:
        sm_mod.select_option_by_value = original

    assert "50" in calls, f"minute '50' must be selected (floor of 55), got {calls}"
