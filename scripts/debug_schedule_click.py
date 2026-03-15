"""
scripts/debug_schedule_click.py
--------------------------------
publish() 흐름을 단계별로 직접 실행하며 어디서 막히는지 정확히 진단.

실행:
    python scripts/debug_schedule_click.py
"""
from __future__ import annotations
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright

NAVER_ID  = os.getenv("NAVER_ID", "")
BLOG_ID   = os.getenv("NAVER_BLOG_ID", "")
SESSION   = os.getenv("SESSION_PATH", f"{NAVER_ID}_session.json")
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&"

G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[1m"; D="\033[2m"; X="\033[0m"

def step(n, title):
    print(f"\n{B}[Step {n}] {title}{X}")

def ok(msg):   print(f"  {G}✅ {msg}{X}")
def fail(msg): print(f"  {R}❌ {msg}{X}")
def info(msg): print(f"  {D}   {msg}{X}")

def try_click(label, locator, timeout=3000):
    try:
        cnt = locator.count()
        if cnt == 0:
            fail(f"{label} → count=0, 요소 없음")
            return False
        vis = locator.first.is_visible()
        if not vis:
            fail(f"{label} → count={cnt}, visible=False")
            return False
        locator.first.click(timeout=timeout)
        ok(f"{label} → 클릭 성공 (count={cnt})")
        return True
    except Exception as e:
        fail(f"{label} → {e}")
        return False

def try_select(label, locator, value, timeout=3000):
    try:
        cnt = locator.count()
        if cnt == 0:
            fail(f"{label} select '{value}' → count=0")
            return False
        locator.first.select_option(value=value, timeout=timeout)
        ok(f"{label} select '{value}' → 성공")
        return True
    except Exception as e:
        fail(f"{label} select '{value}' → {e}")
        return False

def probe_radios(frame, label):
    """현재/예약 라디오 상태 스냅샷"""
    try:
        radios = frame.locator("input[type=radio][name=radio_time]")
        cnt = radios.count()
        info(f"{label}: radio[name=radio_time] count={cnt}")
        for i in range(cnt):
            r = radios.nth(i)
            val = r.get_attribute("value") or "?"
            vis = r.is_visible()
            chk = r.is_checked()
            info(f"  [{i}] value={val!r:6s} visible={vis} checked={chk}")
        return cnt > 0
    except Exception as e:
        fail(f"{label} probe 실패: {e}")
        return False

def main():
    if not BLOG_ID:
        print(f"{R}오류: .env에 NAVER_BLOG_ID 필요{X}"); sys.exit(1)

    target = datetime.now().astimezone()
    target = target.replace(minute=(target.minute // 10) * 10, second=0, microsecond=0)
    target += timedelta(hours=2)
    hour_str   = str(target.hour)
    minute_str = f"{(target.minute // 10) * 10:02d}"

    print(f"\n{B}예약 발행 클릭 단계별 디버그{X}")
    print(f"  목표 시각: {target.strftime('%H:%M')} (hour={hour_str}, min={minute_str})")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=300)
        ctx_kw = {"locale": "ko-KR", "timezone_id": "Asia/Seoul"}
        if Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
        ctx  = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        # ── Step 1: 에디터 열기 ───────────────────────────────────────────
        step(1, "에디터 열기")
        page.goto(WRITE_URL)
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
        time.sleep(2)
        ok(f"URL: {page.url[:60]}")

        frame = page.frame_locator("#mainFrame").first

        # ── Step 2: 발행 버튼 클릭 ────────────────────────────────────────
        step(2, "발행 버튼 클릭 (팝오버 열기)")
        clicked = False
        for ctx_label, loc in [
            ("page",  page.get_by_role("button", name="발행")),
            ("frame", frame.get_by_role("button", name="발행")),
        ]:
            if try_click(f"{ctx_label}.button[발행]", loc):
                clicked = True; break

        if not clicked:
            fail("발행 버튼을 찾지 못했습니다. 수동으로 클릭 후 Enter.")
            input("  Enter 계속 > ")

        # ── Step 3: 팝오버 렌더링 대기 ───────────────────────────────────
        step(3, "팝오버 렌더링 대기")
        for wait_ms in [500, 1000, 2000, 3000]:
            time.sleep(wait_ms / 1000)
            present = probe_radios(frame, f"frame (after {wait_ms}ms)")
            if present:
                ok(f"{wait_ms}ms 후 라디오 요소 발견")
                break
        else:
            fail("3초 대기 후에도 라디오 요소 없음 → 팝오버 미열림 가능성")

        # ── Step 4: 예약 라디오 클릭 시도 (6가지 방법) ───────────────────
        step(4, "예약 라디오 클릭 시도 (6가지 방법)")

        methods = [
            ("frame.get_by_test_id(preTimeRadioBtn)",
             frame.get_by_test_id("preTimeRadioBtn")),
            ("frame.get_by_role(radio, 예약)",
             frame.get_by_role("radio", name="예약")),
            ("frame.locator(input#radio_time2)",
             frame.locator("input#radio_time2")),
            ("frame.locator(input[value=pre])",
             frame.locator("input[type=radio][value=pre]")),
            ("frame.locator(label[for=radio_time2])",
             frame.locator("label[for='radio_time2']")),
            ("page.frame[1].get_by_test_id",
             page.frames[1].get_by_test_id("preTimeRadioBtn") if len(page.frames) > 1 else None),
        ]

        clicked_radio = False
        for label, loc in methods:
            if loc is None:
                info(f"{label} → frames[1] 없음, 건너뜀")
                continue
            if try_click(label, loc, timeout=2000):
                clicked_radio = True
                break

        time.sleep(0.5)
        probe_radios(frame, "클릭 후 상태")

        if not clicked_radio:
            fail("어떤 방법으로도 예약 라디오를 클릭하지 못했습니다.")
            print(f"\n  {Y}브라우저에서 수동으로 '예약'을 클릭한 뒤 Enter를 누르세요.{X}")
            input("  Enter 계속 > ")
            probe_radios(frame, "수동 클릭 후")

        # ── Step 5: 시간 select ───────────────────────────────────────────
        step(5, f"시 선택 (hour={hour_str})")
        hour_methods = [
            ("frame.locator(select[class*=hour_option])",
             frame.locator("select[class*=hour_option]")),
            ("frame.locator(select.hour_option*)",
             frame.locator("select[class^=hour_option]")),
        ]
        if len(page.frames) > 1:
            hour_methods.append((
                "frames[1].locator(select[class*=hour_option])",
                page.frames[1].locator("select[class*=hour_option]"),
            ))

        for label, loc in hour_methods:
            if try_select(label, loc, hour_str):
                break

        # ── Step 6: 분 select ─────────────────────────────────────────────
        step(6, f"분 선택 (minute={minute_str})")
        min_methods = [
            ("frame.locator(select[class*=minute_option])",
             frame.locator("select[class*=minute_option]")),
        ]
        if len(page.frames) > 1:
            min_methods.append((
                "frames[1].locator(select[class*=minute_option])",
                page.frames[1].locator("select[class*=minute_option]"),
            ))

        for label, loc in min_methods:
            if try_select(label, loc, minute_str):
                break

        # ── Step 7: 최종 상태 확인 ────────────────────────────────────────
        step(7, "최종 상태 확인")
        probe_radios(frame, "최종")
        try:
            hour_sel = frame.locator("select[class*=hour_option]").first
            min_sel  = frame.locator("select[class*=minute_option]").first
            info(f"hour select value : {hour_sel.input_value()}")
            info(f"minute select value: {min_sel.input_value()}")
        except Exception as e:
            fail(f"select 값 읽기 실패: {e}")

        print(f"\n{B}브라우저를 확인하세요. Enter로 종료합니다.{X}")
        try: input()
        except (EOFError, KeyboardInterrupt): pass

        browser.close()

if __name__ == "__main__":
    main()
