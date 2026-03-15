"""
tests/test_schedule_e2e.py
--------------------------
예약 발행 UI 흐름 전용 E2E 테스트.

검증 대상:
  - 발행 팝오버가 열린 뒤 "예약" 라디오가 실제로 선택되는지
  - 시/분 select 값이 schedule_at 기준으로 정확히 설정되는지
  - random_window 모드에서 분이 10의 배수로 내림되는지
  - 팝오버가 열린 채로 dry_run 종료되는지 (confirm 미클릭)

전제 조건:
  - session_state.json (또는 .env NAVER_ID/PW/BLOG_ID) 유효
  - 브라우저가 열리고 실제 네이버 에디터에 접속

Run:
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s
    pytest tests/test_schedule_e2e.py -m "e2e and slow" -v -s   # 느린 것만
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from automator.options import AccountOption, MetaOption, TitleOption, ContentOption, RunSetting, KST
from automator.selector_loader import SelectorLoader
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID", "")
NAVER_PW      = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH", "session_state.json")

_MAIN_FRAME = "#mainFrame"
_LOGIN_SEL  = SelectorLoader.load("selectors/naver/login.json")


# ---------------------------------------------------------------------------
# Fixtures — session-scoped browser/context, function-scoped page
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def account() -> AccountOption:
    if not NAVER_BLOG_ID:
        if not os.path.exists(SESSION_PATH):
            pytest.skip("Set NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env or provide session_state.json")
    return AccountOption(
        naver_id=NAVER_ID,
        naver_pw=NAVER_PW,
        blog_id=NAVER_BLOG_ID,
        session_path=SESSION_PATH,
    )


@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser, account: AccountOption):
    if os.path.exists(account.resolved_session_path):
        ctx = browser_instance.new_context(
            storage_state=account.resolved_session_path,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
    else:
        ctx  = browser_instance.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
        page = ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        _LOGIN_SEL.locator(page, "naver_login_id").fill(account.naver_id)
        _LOGIN_SEL.locator(page, "naver_login_pw").fill(account.naver_pw)
        _LOGIN_SEL.locator(page, "naver_login_submit").click()
        page.wait_for_url(lambda url: "nidlogin" not in url, timeout=15_000)
        ctx.storage_state(path=account.resolved_session_path)
        page.close()
    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext):
    p = auth_context.new_page()
    yield p
    p.close()


@pytest.fixture
def editor(page: Page, account: AccountOption) -> SmartEditorOne:
    """dry_run=True — 팝오버는 열리지만 실제 발행하기 버튼은 누르지 않는다."""
    return SmartEditorOne(page, account.write_url, dry_run=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _future_rounded(hours: int = 2, jitter_minutes: int = 0) -> datetime:
    """
    현재 시각 기준 +hours 뒤, 분을 10의 배수로 내림한 KST datetime.
    jitter_minutes가 있으면 그만큼 더 추가한다 (random_window 검증용).
    """
    now = datetime.now(tz=KST)
    base = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
    return base + timedelta(hours=hours, minutes=jitter_minutes)


def _read_popover_state(page: Page) -> dict:
    """
    팝오버 DOM에서 현재 선택된 라디오/시/분 값을 읽어 반환.

    Returns:
        {
            "radio_value":  "now" | "pre" | None,
            "hour_value":   "0"–"23" | None,
            "minute_value": "00"|"10"|…|"50" | None,
        }
    """
    frame = page.frames[1] if len(page.frames) > 1 else page.main_frame
    return frame.evaluate("""() => {
        const checked = document.querySelector(
            'input[name="radio_time"]:checked'
        );
        const hourSel = document.querySelector('select[class*=hour_option]');
        const minSel  = document.querySelector('select[class*=minute_option]');
        return {
            radio_value:  checked  ? checked.value  : null,
            hour_value:   hourSel  ? hourSel.value   : null,
            minute_value: minSel   ? minSel.value    : null,
        };
    }""")


def _open_editor_and_publish_popover(editor: SmartEditorOne) -> None:
    """에디터를 열고 발행 팝오버만 띄운다 (제목/본문은 비워둠)."""
    editor.open()
    editor._click_publish_trigger()
    editor._wait_for_popover_ready()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_popover_opens_with_now_selected_by_default(editor: SmartEditorOne, page: Page):
    """
    발행 팝오버를 열었을 때 기본값은 "현재" 라디오가 선택돼 있어야 한다.
    예약을 건드리기 전 baseline을 검증한다.
    """
    _open_editor_and_publish_popover(editor)

    state = _read_popover_state(page)
    assert state["radio_value"] == "now", (
        f"기본 선택이 'now'여야 한다 (got {state['radio_value']!r})"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_scheduled_radio_is_selected_after_set(editor: SmartEditorOne, page: Page):
    """
    _set_scheduled_publish() 호출 후 "예약" 라디오(value='pre')가
    실제로 선택돼 있는지 DOM에서 확인한다.
    """
    target = _future_rounded(hours=2)
    _open_editor_and_publish_popover(editor)
    editor._set_scheduled_publish(target)

    state = _read_popover_state(page)
    assert state["radio_value"] == "pre", (
        f"'예약' 라디오(value=pre)가 선택돼야 한다 (got {state['radio_value']!r})"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_hour_select_matches_schedule_at(editor: SmartEditorOne, page: Page):
    """
    _set_scheduled_publish() 후 시간 select 값이 schedule_at.hour와 일치한다.
    """
    target = _future_rounded(hours=3)
    expected_hour = f"{target.hour:02d}"

    _open_editor_and_publish_popover(editor)
    editor._set_scheduled_publish(target)

    state = _read_popover_state(page)
    assert state["hour_value"] == expected_hour, (
        f"hour select가 {expected_hour!r}여야 한다 (got {state['hour_value']!r})"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_minute_select_matches_floored_schedule_at(editor: SmartEditorOne, page: Page):
    """
    _set_scheduled_publish() 후 분 select 값이 schedule_at.minute을
    10의 배수로 내림한 값과 일치한다.
    예: schedule_at.minute=37 → select value="30"
    """
    # minute이 10의 배수가 아닌 시각을 강제로 만든다
    now    = datetime.now(tz=KST)
    # 현재 분 + 5 (10 배수 아님) 으로 target 분 설정, 2시간 뒤
    raw_minute = (now.minute + 5) % 60
    target = now.replace(minute=raw_minute, second=0, microsecond=0) + timedelta(hours=2)
    expected_minute = f"{(raw_minute // 10) * 10:02d}"

    _open_editor_and_publish_popover(editor)
    editor._set_scheduled_publish(target)

    state = _read_popover_state(page)
    assert state["minute_value"] == expected_minute, (
        f"minute select가 {expected_minute!r}여야 한다 "
        f"(raw={raw_minute}, got {state['minute_value']!r})"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_full_schedule_state_via_publish(editor: SmartEditorOne, page: Page):
    """
    publish(schedule_at=...) 전체 흐름 후 팝오버 DOM 상태를 한 번에 검증.

    검증 항목:
      1. radio_value == "pre"
      2. hour_value  == str(schedule_at.hour)
      3. minute_value == floored minute (zero-padded)
      4. 팝오버가 열린 채로 유지됨 (dry_run — confirm 미클릭)
    """
    target = _future_rounded(hours=2)
    expected_hour   = f"{target.hour:02d}"
    expected_minute = f"{(target.minute // 10) * 10:02d}"

    # publish() 전체 흐름 실행 (dry_run=True → confirm 스킵)
    editor.open()
    editor.publish(schedule_at=target)

    state = _read_popover_state(page)

    assert state["radio_value"]  == "pre",          f"radio: {state['radio_value']!r}"
    assert state["hour_value"]   == expected_hour,  f"hour: {state['hour_value']!r} (want {expected_hour!r})"
    assert state["minute_value"] == expected_minute, f"minute: {state['minute_value']!r} (want {expected_minute!r})"


@pytest.mark.e2e
@pytest.mark.slow
def test_schedule_via_job_fixed_mode(page: Page, account: AccountOption):
    """
    NaverBlogJob + MetaOption(schedule_mode='fixed')으로 실행했을 때
    팝오버 DOM이 올바르게 설정되는지 검증.

    dry_run=True이므로 실제 발행 없음.
    """
    target = _future_rounded(hours=2)
    expected_hour   = f"{target.hour:02d}"
    expected_minute = f"{(target.minute // 10) * 10:02d}"

    editor = SmartEditorOne(page, account.write_url, dry_run=True)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="예약 발행 테스트"))
        .with_content(ContentOption(layout=["Paragraph 1"]))
        .with_meta(MetaOption(
            schedule_mode="fixed",
            schedule_at=target,
        ))
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True

    state = _read_popover_state(page)
    assert state["radio_value"]  == "pre",          f"radio: {state['radio_value']!r}"
    assert state["hour_value"]   == expected_hour,  f"hour: {state['hour_value']!r}"
    assert state["minute_value"] == expected_minute, f"minute: {state['minute_value']!r}"


@pytest.mark.e2e
@pytest.mark.slow
def test_schedule_via_job_random_window_mode(page: Page, account: AccountOption):
    """
    NaverBlogJob + MetaOption(schedule_mode='random_window')으로 실행했을 때
    팝오버 DOM의 시/분이 [center - jitter, center + jitter] 범위 안에 있는지 검증.

    random_window는 실행마다 다른 시각이 선택되므로 범위 검증을 사용한다.
    분은 항상 10의 배수여야 한다 (_round_minute_to_10).
    """
    center       = _future_rounded(hours=3)
    jitter       = 30  # minutes
    earliest     = center - timedelta(minutes=jitter)
    latest       = center + timedelta(minutes=jitter)

    editor = SmartEditorOne(page, account.write_url, dry_run=True)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="예약 발행 random_window 테스트"))
        .with_content(ContentOption(layout=["Paragraph 1"]))
        .with_meta(MetaOption(
            schedule_mode="random_window",
            schedule_at=center,
            schedule_jitter_minutes=jitter,
        ))
        .with_setting(RunSetting())
    )
    assert job.run(editor) is True

    state = _read_popover_state(page)

    # radio는 반드시 "pre"
    assert state["radio_value"] == "pre", f"radio: {state['radio_value']!r}"

    # 시/분을 datetime으로 재조합해서 범위 검증
    assert state["hour_value"]   is not None, "hour select 값 없음"
    assert state["minute_value"] is not None, "minute select 값 없음"

    resolved_hour   = int(state["hour_value"])
    resolved_minute = int(state["minute_value"])

    # 분이 10의 배수인지 확인
    assert resolved_minute % 10 == 0, (
        f"분은 항상 10의 배수여야 한다 (got {resolved_minute})"
    )

    # 날짜는 center와 같은 날로 가정 (자정 경계 케이스 제외)
    resolved_dt = center.replace(
        hour=resolved_hour, minute=resolved_minute, second=0, microsecond=0
    )

    # 범위: [earliest의 분 내림, latest의 분 올림(+10)] 내에 있어야 함
    earliest_floored = earliest.replace(
        minute=(earliest.minute // 10) * 10, second=0, microsecond=0
    )
    latest_ceiled = latest.replace(
        minute=(latest.minute // 10) * 10, second=0, microsecond=0
    ) + timedelta(minutes=10)

    assert earliest_floored <= resolved_dt <= latest_ceiled, (
        f"resolved={resolved_dt.strftime('%H:%M')}이 "
        f"[{earliest_floored.strftime('%H:%M')}, {latest_ceiled.strftime('%H:%M')}] 범위 밖"
    )

