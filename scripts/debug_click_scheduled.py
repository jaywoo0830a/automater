"""
scripts/debug_click_scheduled.py
----------------------------------
팝오버가 열린 상태에서 '예약' 라디오를 클릭하는 모든 방법을 시험한다.

수행 순서
---------
1. 에디터 오픈 → 발행 팝오버 열기
2. 아래 방법을 순서대로 시도하여 첫 번째 성공한 방법을 보고한다:
   A. frame_locator.get_by_test_id("preTimeRadioBtn")
   B. frame_locator.get_by_role("radio", name="예약")
   C. frame_locator.locator("input[name=radio_time][value=pre]")
   D. frame_locator.locator("#radio_time2")
   E. JS click via frame.evaluate (Frame 객체 직접 사용)
   F. JS click via page.evaluate (top-level)
3. 각 시도마다 count / is_visible / click 결과를 출력한다.
4. 성공한 방법을 editor.json 형식으로 출력한다.

실행
----
    python scripts/debug_click_scheduled.py

Prerequisites
-------------
  - .env에 NAVER_BLOG_ID, NAVER_ID 또는 session_state.json
"""

from __future__ import annotations
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright

NAVER_ID  = os.getenv("NAVER_ID",      "")
BLOG_ID   = os.getenv("NAVER_BLOG_ID", "")
SESSION   = os.getenv("SESSION_PATH",  f"{NAVER_ID}_session.json")
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

# ---------------------------------------------------------------------------
# 발행 팝오버 열기
# ---------------------------------------------------------------------------
def open_popover(page):
    print(f"\n  {Y}발행 버튼 클릭...{X}")
    for ctx in (page, page.frame_locator("#mainFrame").first):
        try:
            btn = ctx.get_by_role("button", name="발행")
            if btn.count() > 0:
                btn.first.click()
                print(f"  {G}✅ 발행 버튼 클릭됨{X}")
                time.sleep(2.5)   # 팝오버 완전 렌더링 대기
                return True
        except Exception:
            pass
    print(f"  {R}❌ 발행 버튼을 찾지 못했습니다{X}")
    return False

# ---------------------------------------------------------------------------
# 단일 로케이터 시험
# ---------------------------------------------------------------------------
def try_locator(label: str, locator, do_click: bool = True) -> bool:
    try:
        count   = locator.count()
        visible = locator.first.is_visible() if count > 0 else False
        print(f"  {label:55s} count={count}, visible={visible}", end="")
        if count == 0 or not visible:
            print(f"  {R}→ 스킵{X}")
            return False
        if do_click:
            locator.first.click()
            time.sleep(0.5)
            # 클릭 후 체크 여부로 성공 판단
            checked = locator.first.is_checked()
            if checked:
                print(f"  {G}→ 클릭 성공 ✅ (checked={checked}){X}")
            else:
                print(f"  {Y}→ 클릭했으나 checked=False{X}")
            return checked
        print()
        return True
    except Exception as e:
        print(f"  {R}→ 오류: {e}{X}")
        return False

# ---------------------------------------------------------------------------
# JS 직접 클릭
# ---------------------------------------------------------------------------
def try_js_click(label: str, frame_or_page, selector: str) -> bool:
    try:
        result = frame_or_page.evaluate(f"""() => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'not found';
            el.click();
            return 'clicked:' + el.checked;
        }}""")
        success = str(result).startswith("clicked:true")
        color = G if success else Y
        print(f"  {label:55s} JS result={result!r}  {color}{'✅' if success else '△'}{X}")
        return success
    except Exception as e:
        print(f"  {label:55s} {R}JS 오류: {e}{X}")
        return False

# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main():
    if not BLOG_ID:
        print(f"{R}오류: .env에 NAVER_BLOG_ID 필요{X}"); sys.exit(1)

    print(f"\n{B}예약 라디오 클릭 집중 디버그{X}")
    print(f"  URL  : {WRITE_URL}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=100)
        ctx_kw: dict = {"locale": "ko-KR", "timezone_id": "Asia/Seoul"}
        if Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
        ctx  = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        print(f"\n  {Y}에디터 오픈...{X}")
        page.goto(WRITE_URL)
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
        time.sleep(2)

        if "login" in page.url or "nid.naver.com" in page.url:
            print(f"  {R}로그인 필요. session_state.json을 확인하세요.{X}")
            browser.close(); sys.exit(1)

        if not open_popover(page):
            print(f"  {R}팝오버 열기 실패{X}")
            browser.close(); sys.exit(1)

        # ── 팝오버 열린 직후 Frame 객체들 준비 ─────────────────────────────
        frame_locator = page.frame_locator("#mainFrame").first   # FrameLocator

        # JS evaluate용 실제 Frame 객체
        js_frame = next(
            (f for f in page.frames if "PostWriteForm" in f.url),
            None
        )
        if js_frame is None and len(page.frames) > 1:
            js_frame = page.frames[1]

        print(f"\n  {C}Frame 정보:{X}")
        print(f"    page.frames 수 : {len(page.frames)}")
        for i, f in enumerate(page.frames):
            print(f"    frames[{i}] : {f.url[:80]}")
        print(f"    JS 평가용 frame : {js_frame.url[:80] if js_frame else '없음'}")

        # ── 방법 A~F 순서대로 시험 ──────────────────────────────────────────
        print(f"\n{B}── 클릭 방법 시험 ─────────────────────────────────────────────{X}")
        winner = None

        # A. testid via FrameLocator
        print(f"\n  {C}[A] FrameLocator.get_by_test_id('preTimeRadioBtn'){X}")
        if try_locator("  A-1. frame_locator.get_by_test_id",
                       frame_locator.get_by_test_id("preTimeRadioBtn")):
            winner = "A"; 

        # B. role+name via FrameLocator
        if not winner:
            print(f"\n  {C}[B] FrameLocator.get_by_role('radio', name='예약'){X}")
            if try_locator("  B-1. frame_locator.get_by_role radio 예약",
                           frame_locator.get_by_role("radio", name="예약")):
                winner = "B"

        # C. CSS attribute selector via FrameLocator
        if not winner:
            print(f"\n  {C}[C] FrameLocator.locator('input[name=radio_time][value=pre]'){X}")
            if try_locator("  C-1. frame_locator css attr selector",
                           frame_locator.locator("input[name=radio_time][value=pre]")):
                winner = "C"

        # D. ID selector via FrameLocator
        if not winner:
            print(f"\n  {C}[D] FrameLocator.locator('#radio_time2'){X}")
            if try_locator("  D-1. frame_locator #radio_time2",
                           frame_locator.locator("#radio_time2")):
                winner = "D"

        # E. JS click via actual Frame object
        if not winner and js_frame:
            print(f"\n  {C}[E] JS click via frame.evaluate (실제 Frame 객체){X}")
            if try_js_click(
                "  E-1. frame.evaluate input[name=radio_time][value=pre]",
                js_frame, "input[name=radio_time][value=pre]"
            ):
                winner = "E"

            if not winner:
                if try_js_click("  E-2. frame.evaluate #radio_time2",
                                js_frame, "#radio_time2"):
                    winner = "E-2"

            if not winner:
                if try_js_click("  E-3. frame.evaluate data-testid",
                                js_frame, "[data-testid=preTimeRadioBtn]"):
                    winner = "E-3"

        # F. JS click via page.evaluate (top-level, searches all frames)
        if not winner:
            print(f"\n  {C}[F] page.evaluate로 모든 프레임 순회 클릭{X}")
            try:
                result = page.evaluate("""() => {
                    for (const frame of window.frames) {
                        try {
                            const el = frame.document.querySelector(
                                'input[name=radio_time][value=pre]'
                            );
                            if (el) { el.click(); return 'clicked:' + el.checked; }
                        } catch(e) {}
                    }
                    return 'not found in any frame';
                }""")
                print(f"  F-1. page.evaluate frames loop : {result!r}", end="")
                if "clicked:true" in str(result):
                    print(f"  {G}✅{X}")
                    winner = "F"
                else:
                    print(f"  {Y}△{X}")
            except Exception as e:
                print(f"  {R}오류: {e}{X}")

        # ── 추가: label 클릭 (label for=radio_time2) ──────────────────────
        if not winner:
            print(f"\n  {C}[G] label[for=radio_time2] 클릭 (FrameLocator){X}")
            if try_locator("  G-1. frame_locator label[for=radio_time2]",
                           frame_locator.locator("label[for=radio_time2]")):
                winner = "G"

        if not winner and js_frame:
            print(f"\n  {C}[H] JS click label[for=radio_time2]{X}")
            if try_js_click("  H-1. frame.evaluate label[for=radio_time2]",
                            js_frame, "label[for=radio_time2]"):
                winner = "H"

        # ── 결과 요약 ────────────────────────────────────────────────────────
        print(f"\n{'='*64}")
        if winner:
            print(f"  {G}{B}성공한 방법: [{winner}]{X}")
            WINNER_MAP = {
                "A":   ("testid", "preTimeRadioBtn", "FrameLocator"),
                "B":   ("role+name", "radio / 예약", "FrameLocator"),
                "C":   ("css", "input[name=radio_time][value=pre]", "FrameLocator"),
                "D":   ("css", "#radio_time2", "FrameLocator"),
                "E":   ("js_evaluate", "input[name=radio_time][value=pre]", "Frame.evaluate"),
                "E-2": ("js_evaluate", "#radio_time2", "Frame.evaluate"),
                "E-3": ("js_evaluate", "[data-testid=preTimeRadioBtn]", "Frame.evaluate"),
                "F":   ("js_evaluate", "window.frames loop", "page.evaluate"),
                "G":   ("css", "label[for=radio_time2]", "FrameLocator"),
                "H":   ("js_evaluate", "label[for=radio_time2]", "Frame.evaluate"),
            }
            info = WINNER_MAP.get(winner, ("?", "?", "?"))
            print(f"\n  editor.json에 적용할 셀렉터:")
            print(f'  "publish_scheduled": {{')
            print(f'    "locators": [{{"type": "{info[0]}", "value": "{info[1]}"}}]')
            print(f'  }}')
            print(f"  컨텍스트: {info[2]}")
        else:
            print(f"  {R}{B}모든 방법 실패 — 브라우저 DevTools로 직접 확인 필요{X}")

        print(f"\n{B}브라우저를 직접 확인하세요.{X}")
        try:
            input(f"  {D}[Enter] 종료{X} ")
        except (EOFError, KeyboardInterrupt):
            pass

        browser.close()

    print(f"\n{G}{B}완료{X}")

if __name__ == "__main__":
    main()
