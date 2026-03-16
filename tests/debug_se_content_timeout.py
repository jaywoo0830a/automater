"""
tests/debug_se_content_timeout.py
-----------------------------------
디버그 테스트 — .se-content TimeoutError 원인 추적.

증상:
    test_scheduled_radio_is_selected_after_set
    test_hour_select_matches_schedule_at
    → TimeoutError: Locator.wait_for: .se-content visible 30s 초과

가설:
    A. 팝오버 열린 채 다음 테스트 진입 → 에디터 재로드 불가
    B. 로그인 세션 만료 → 로그인 페이지로 리다이렉트
    C. .se-content 로드 자체가 30초 초과 (네트워크 문제)
    D. 연속 open() 호출 시 두 번째 실패

실행:
    bash ./run/test.sh --debug-se
"""

import time
import pytest
from playwright.sync_api import Page
from automator.smart_editor import SmartEditorOne
from automator.options import AccountOption


# ---------------------------------------------------------------------------
# [A] 팝오버가 열린 상태에서 editor.open() 재호출
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_open_after_popover_is_still_visible(page: Page, account: AccountOption):
    """
    [DEBUG-A] 팝오버를 열어둔 채로 editor.open() 을 다시 호출했을 때
    .se-content 가 보이는지 확인.
    실패하면 가설 A 확인 — 이전 테스트가 팝오버를 닫지 않은 것이 원인.
    """
    editor = SmartEditorOne(page, account.write_url, dry_run=True)
    editor.open()

    editor._click_publish_trigger()
    editor._wait_for_popover_ready()
    print(f"\n[DEBUG-A] 팝오버 열림. URL: {page.url}")
    print("[DEBUG-A] 팝오버를 닫지 않고 editor.open() 재호출...")

    try:
        editor.open()
        print("[DEBUG-A] ✅ 재호출 성공 — 팝오버 미닫힘은 원인 아님")
    except Exception as e:
        print(f"[DEBUG-A] ❌ 재호출 실패 → 가설 A 확인: {e}")
        raise


# ---------------------------------------------------------------------------
# [B] 로그인 세션 유효성 확인
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_session_alive(page: Page, account: AccountOption):
    """
    [DEBUG-B] 에디터 URL 로 이동 후 로그인 페이지 리다이렉트 여부 확인.
    실패하면 가설 B — bash ./run/dev.sh --session 으로 세션 재저장 필요.
    """
    page.goto(account.write_url, wait_until="domcontentloaded", timeout=30_000)
    final_url = page.url
    print(f"\n[DEBUG-B] 이동 후 URL: {final_url}")

    is_login = "nidlogin" in final_url or "login" in final_url.lower()
    print(f"[DEBUG-B] {'❌ 세션 만료 (로그인 페이지)' if is_login else '✅ 세션 유효'}")

    assert not is_login, (
        f"세션 만료 → 로그인 페이지 리다이렉트: {final_url}\n"
        "bash ./run/dev.sh --session 으로 세션을 다시 저장하세요."
    )


# ---------------------------------------------------------------------------
# [C] .se-content 로드 시간 측정
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_se_content_load_time(page: Page, account: AccountOption):
    """
    [DEBUG-C] .se-content 가 실제로 몇 초 만에 나타나는지 측정.
    30초 초과 시 smart_editor.py 의 타임아웃 상향 필요.
    """
    page.goto(account.write_url, wait_until="domcontentloaded", timeout=30_000)
    print(f"\n[DEBUG-C] 로드 완료: {page.url}")

    frames = page.frames
    print(f"[DEBUG-C] 프레임 수: {len(frames)}")
    for i, f in enumerate(frames):
        print(f"  [{i}] {f.url[:80]}")

    # 에디터 프레임 찾기
    editor_frame = next(
        (f for f in frames if any(k in f.url for k in ("SmartEditor", "PostWrite", "se2"))),
        frames[1] if len(frames) > 1 else page.main_frame
    )
    print(f"[DEBUG-C] 에디터 프레임: {editor_frame.url[:80]}")

    start = time.time()
    try:
        editor_frame.locator(".se-content").wait_for(state="visible", timeout=60_000)
        elapsed = time.time() - start
        print(f"[DEBUG-C] ✅ .se-content visible — {elapsed:.1f}초 소요")
        if elapsed > 25:
            print("[DEBUG-C] ⚠️  30초 타임아웃에 근접 — 타임아웃 상향 필요")
    except Exception as e:
        elapsed = time.time() - start
        print(f"[DEBUG-C] ❌ {elapsed:.1f}초 후 실패: {e}")
        raise


# ---------------------------------------------------------------------------
# [D] 연속 두 번 open() 호출
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_consecutive_open(page: Page, account: AccountOption):
    """
    [DEBUG-D] editor.open() 을 연속 두 번 호출해서 두 번째도 성공하는지 확인.
    실패하면 가설 D — open() 자체에 재진입 버그 존재.
    """
    editor = SmartEditorOne(page, account.write_url, dry_run=True)

    print("\n[DEBUG-D] 첫 번째 open()...")
    editor.open()
    print("[DEBUG-D] ✅ 첫 번째 성공")

    print("[DEBUG-D] 두 번째 open()...")
    editor.open()
    print("[DEBUG-D] ✅ 두 번째 성공")
