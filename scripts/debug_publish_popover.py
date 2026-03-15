"""
scripts/debug_publish_popover.py
----------------------------------
발행 팝오버 내 '현재'/'예약' 요소를 찾지 못하는 문제 진단 스크립트.

수행 내용
---------
1. 세션으로 에디터 오픈
2. 발행 버튼 클릭 → 팝오버 열기
3. page / mainFrame / 모든 서브프레임 각각에서:
   - radio 요소 전체 목록 출력 (aria-label, name, id, class)
   - '현재' / '예약' 텍스트를 포함하는 요소 전체 출력
   - 현재 JSON 셀렉터 4종 직접 시도 결과 출력
4. 성공한 셀렉터를 editor.json에 바로 적용할 수 있는 형태로 출력

실행
----
    python scripts/debug_publish_popover.py

Prerequisites
-------------
  - .env에 NAVER_ID / NAVER_PW / NAVER_BLOG_ID 또는 session_state.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright, Page, Frame

# ── config ─────────────────────────────────────────────────────────────────
NAVER_ID  = os.getenv("NAVER_ID",      "")
NAVER_PW  = os.getenv("NAVER_PW",      "")
BLOG_ID   = os.getenv("NAVER_BLOG_ID", "")
SESSION   = os.getenv("SESSION_PATH",  f"{NAVER_ID}_session.json")
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&"

# ── ANSI ───────────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

DIVIDER = f"{D}{'─' * 64}{X}"


# ---------------------------------------------------------------------------
# DOM 탐색 JS
# ---------------------------------------------------------------------------

# 모든 radio / checkbox input 수집
_JS_ALL_RADIOS = """() => {
    const results = [];
    const inputs = document.querySelectorAll('input[type=radio], input[type=checkbox]');
    inputs.forEach(el => {
        // label 연결 텍스트
        let labelText = '';
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) labelText = lbl.innerText.trim();
        }
        if (!labelText && el.closest('label')) {
            labelText = el.closest('label').innerText.trim();
        }
        // aria-labelledby
        const llby = el.getAttribute('aria-labelledby');
        let llbyText = '';
        if (llby) {
            const ref = document.getElementById(llby);
            if (ref) llbyText = ref.innerText.trim();
        }
        results.push({
            tag:          'input',
            type:         el.type,
            id:           el.id,
            name:         el.name,
            value:        el.value,
            checked:      el.checked,
            ariaLabel:    el.getAttribute('aria-label') || '',
            ariaLabelledBy: llby || '',
            llbyText:     llbyText,
            labelText:    labelText,
            classes:      el.className,
            outerHTML:    el.outerHTML.slice(0, 200),
        });
    });
    return results;
}"""

# '현재' 또는 '예약' 텍스트를 포함하는 요소 수집
_JS_TEXT_MATCH = """() => {
    const keywords = ['현재', '예약'];
    const results  = [];
    const seen     = new Set();

    const walk = (el) => {
        if (seen.has(el)) return;
        seen.add(el);
        const text = (el.innerText || el.textContent || '').trim();
        if (!text) return;
        const lower = text.toLowerCase();
        if (keywords.some(k => text.includes(k)) && text.length < 30) {
            results.push({
                tag:       el.tagName.toLowerCase(),
                role:      el.getAttribute('role') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                id:        el.id,
                classes:   el.className,
                text:      text.slice(0, 60),
                outerHTML: el.outerHTML.slice(0, 300),
            });
        }
        for (const child of el.children) walk(child);
    };
    walk(document.body);
    return results;
}"""

# select 요소 전체 수집 (시/분 드롭다운 탐색용)
_JS_ALL_SELECTS = """() => {
    return [...document.querySelectorAll('select')].map(el => ({
        id:        el.id,
        name:      el.name,
        classes:   el.className,
        ariaLabel: el.getAttribute('aria-label') || '',
        options:   [...el.options].map(o => o.value).slice(0, 10),
        outerHTML: el.outerHTML.slice(0, 200),
    }));
}"""

# 특정 role+name 으로 요소 존재 여부 확인 (aria-*)
_JS_ROLE_QUERY = """(args) => {
    const [role, name] = args;
    // querySelector by role
    const byRole = document.querySelectorAll('[role="' + role + '"]');
    const matched = [...byRole].filter(el => {
        const label = el.getAttribute('aria-label') || el.innerText || '';
        return label.includes(name);
    });
    // also check native elements
    let native = [];
    if (role === 'radio') {
        native = [...document.querySelectorAll('input[type=radio]')].filter(el => {
            const lbl = el.id
                ? document.querySelector('label[for="' + el.id + '"]')
                : el.closest('label');
            return lbl && lbl.innerText.includes(name);
        });
    }
    return {
        byRole: matched.map(el => el.outerHTML.slice(0, 200)),
        native: native.map(el => el.outerHTML.slice(0, 200)),
    };
}"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    print(f"\n{B}{Y}▶ {title}{X}")
    print(DIVIDER)


def _run_js(ctx, js: str, arg=None):
    """ctx = playwright Frame object (has evaluate())"""
    try:
        if arg is None:
            return ctx.evaluate(js)
        return ctx.evaluate(js, arg)
    except Exception as e:
        return f"[JS ERROR] {e}"


def _try_playwright_locator(ctx, description: str, locator) -> bool:
    """Playwright locator 접근 가능 여부 확인. ctx는 표시용 이름."""
    try:
        count = locator.count()
        visible = locator.first.is_visible() if count > 0 else False
        status = f"{G}✅ count={count}, visible={visible}{X}"
        print(f"  {description:45s} {status}")
        return count > 0
    except Exception as e:
        print(f"  {description:45s} {R}❌ {e}{X}")
        return False


def _probe_context(label: str, ctx) -> None:
    """한 컨텍스트(page or frame)에 대해 전수 탐색"""
    print(f"\n  {C}{B}[{label}]{X}")

    # --- radio 요소 ---
    radios = _run_js(ctx, _JS_ALL_RADIOS)
    if isinstance(radios, list) and radios:
        print(f"  {D}  radio/checkbox 요소 ({len(radios)}개):{X}")
        for r in radios:
            print(f"    id={r['id']!r:20s} name={r['name']!r:15s} "
                  f"value={r['value']!r:10s} label={r['labelText']!r:10s} "
                  f"aria={r['ariaLabel']!r:10s} class={r['classes'][:40]!r}")
    else:
        print(f"  {D}  radio/checkbox 요소 없음{X}")

    # --- 현재/예약 텍스트 요소 ---
    text_matches = _run_js(ctx, _JS_TEXT_MATCH)
    if isinstance(text_matches, list) and text_matches:
        print(f"  {D}  '현재'/'예약' 텍스트 포함 요소 ({len(text_matches)}개):{X}")
        for m in text_matches:
            print(f"    <{m['tag']}> role={m['role']!r:10s} "
                  f"id={m['id']!r:15s} text={m['text']!r:15s}")
            print(f"      {D}{m['outerHTML'][:120]}{X}")
    else:
        print(f"  {D}  '현재'/'예약' 텍스트 요소 없음{X}")

    # --- select 요소 ---
    selects = _run_js(ctx, _JS_ALL_SELECTS)
    if isinstance(selects, list) and selects:
        print(f"  {D}  select 요소 ({len(selects)}개):{X}")
        for s in selects:
            print(f"    id={s['id']!r:20s} class={s['classes'][:40]!r} "
                  f"options={s['options'][:6]}")
    else:
        print(f"  {D}  select 요소 없음{X}")

    # --- role+name 직접 쿼리 ---
    for role, name in [("radio", "현재"), ("radio", "예약"),
                       ("button", "현재"), ("button", "예약")]:
        result = _run_js(ctx, _JS_ROLE_QUERY, [role, name])
        if isinstance(result, dict):
            total = len(result.get("byRole", [])) + len(result.get("native", []))
            if total:
                print(f"  {G}  role={role!r} name={name!r} → {total}개 발견{X}")
                for html in (result["byRole"] + result["native"])[:3]:
                    print(f"    {D}{html[:150]}{X}")


def _probe_playwright_locators(page) -> None:
    """Playwright API로 현재 JSON 셀렉터 4종 직접 시도"""
    _section("Playwright 로케이터 직접 시도 (page / mainFrame)")

    contexts = {
        "page": page,
        "mainFrame": page.frame_locator("#mainFrame").first,
    }

    checks = [
        # (description, locator_fn)
        ("radio name='현재'",       lambda ctx: ctx.get_by_role("radio",  name="현재")),
        ("radio name='예약'",       lambda ctx: ctx.get_by_role("radio",  name="예약")),
        ("label name='현재'",       lambda ctx: ctx.get_by_role("label",  name="현재")),
        ("label name='예약'",       lambda ctx: ctx.get_by_role("label",  name="예약")),
        ("button name='현재'",      lambda ctx: ctx.get_by_role("button", name="현재")),
        ("button name='예약'",      lambda ctx: ctx.get_by_role("button", name="예약")),
        ("get_by_text('현재')",     lambda ctx: ctx.get_by_text("현재", exact=True)),
        ("get_by_text('예약')",     lambda ctx: ctx.get_by_text("예약", exact=True)),
        ("select.hour_option*",     lambda ctx: ctx.locator("select[class*=hour_option]")),
        ("select.minute_option*",   lambda ctx: ctx.locator("select[class*=minute_option]")),
        ("input[type=radio]",       lambda ctx: ctx.locator("input[type=radio]")),
    ]

    for ctx_label, ctx in contexts.items():
        print(f"\n  {C}{B}[{ctx_label}]{X}")
        for desc, fn in checks:
            try:
                loc = fn(ctx)
                _try_playwright_locator(ctx_label, desc, loc)
            except Exception as e:
                print(f"  {desc:45s} {R}❌ locator() 오류: {e}{X}")


def _probe_all_frames(page) -> None:
    """page.frames 전체를 JS로 탐색"""
    _section(f"모든 프레임 JS 탐색 (총 {len(page.frames)}개)")
    for i, frame in enumerate(page.frames):
        url_short = frame.url[:80] if frame.url else "(no url)"
        _probe_context(f"frame[{i}] {url_short}", frame)


# ---------------------------------------------------------------------------
# 발행 팝오버 열기
# ---------------------------------------------------------------------------

def _open_popover(page) -> bool:
    """발행 버튼 클릭 → 팝오버 열리길 기다림. 성공 여부 반환."""
    print(f"\n  {Y}→ 발행 버튼 클릭 시도...{X}")

    # 1) role=button name=발행 (page 레벨)
    try:
        btn = page.get_by_role("button", name="발행")
        if btn.count() > 0:
            btn.first.click()
            print(f"  {G}✅ page.get_by_role('button', name='발행') 클릭됨{X}")
        else:
            raise RuntimeError("not found")
    except Exception:
        # 2) iframe 안에서 시도
        try:
            btn = page.frame_locator("#mainFrame").first.get_by_role("button", name="발행")
            btn.first.click()
            print(f"  {G}✅ frame.get_by_role('button', name='발행') 클릭됨{X}")
        except Exception as e:
            print(f"  {R}❌ 발행 버튼을 찾지 못했습니다: {e}{X}")
            return False

    # 팝오버 DOM 안정화 대기
    print(f"  {D}  팝오버 열림 대기 (2초)...{X}")
    time.sleep(2)
    return True


# ---------------------------------------------------------------------------
# 요약 출력
# ---------------------------------------------------------------------------

def _print_summary(page) -> None:
    """발견된 셀렉터 후보를 editor.json 형식으로 출력"""
    _section("editor.json 업데이트 후보 요약")

    # 가능한 후보들을 실제로 시도해서 작동하는 것만 출력
    candidates: dict[str, list[dict]] = {
        "publish_scheduled": [],
        "publish_now":       [],
        "publish_scheduled_hour": [],
        "publish_scheduled_min":  [],
    }

    def _add(key: str, loc, entry: dict) -> None:
        try:
            if loc.count() > 0:
                candidates[key].append(entry)
        except Exception:
            pass

    for ctx_label, ctx in [
        ("page", page),
        ("frame", page.frame_locator("#mainFrame").first),
    ]:
        _add("publish_scheduled", ctx.get_by_role("radio",  name="예약"),
             {"type": "role", "value": "radio", "name": "예약"})
        _add("publish_now",       ctx.get_by_role("radio",  name="현재"),
             {"type": "role", "value": "radio", "name": "현재"})
        _add("publish_scheduled", ctx.get_by_text("예약", exact=True),
             {"type": "text", "value": "예약"})
        _add("publish_now",       ctx.get_by_text("현재", exact=True),
             {"type": "text", "value": "현재"})
        _add("publish_scheduled_hour",
             ctx.locator("select[class*=hour_option]"),
             {"type": "css", "value": "select[class*=hour_option]"})
        _add("publish_scheduled_min",
             ctx.locator("select[class*=minute_option]"),
             {"type": "css", "value": "select[class*=minute_option]"})
        # select 전체 (fallback)
        selects = _run_js(
            page.frames[1] if len(page.frames) > 1 else page.main_frame,
            _JS_ALL_SELECTS,
        )
        if isinstance(selects, list):
            for s in selects:
                cls = s.get("classes", "")
                if cls:
                    _add("publish_scheduled_hour",
                         ctx.locator(f"select.{cls.split()[0]}"),
                         {"type": "css", "value": f"select.{cls.split()[0]}"})

    print()
    for key, entries in candidates.items():
        # 중복 제거
        seen = set()
        unique = []
        for e in entries:
            sig = json.dumps(e, sort_keys=True)
            if sig not in seen:
                seen.add(sig)
                unique.append(e)

        status = f"{G}✅ {len(unique)}개 후보{X}" if unique else f"{R}❌ 후보 없음{X}"
        print(f"  {B}\"{key}\"{X}: {status}")
        for e in unique:
            print(f"    {D}{json.dumps(e, ensure_ascii=False)}{X}")

    if any(candidates.values()):
        print(f"\n  {Y}위 후보를 selectors/naver/editor.json에 반영하세요.{X}")
    else:
        print(f"\n  {R}작동하는 셀렉터를 찾지 못했습니다.{X}")
        print(f"  아래 항목을 확인하세요:")
        print(f"  1. 팝오버가 실제로 열렸는지 브라우저를 보고 확인")
        print(f"  2. 팝오버가 추가 iframe 안에 렌더링되지 않는지 확인")
        print(f"  3. '모든 프레임 JS 탐색' 섹션에서 텍스트 매칭 결과 확인")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    if not BLOG_ID:
        print(f"{R}오류: .env에 NAVER_BLOG_ID가 필요합니다.{X}")
        sys.exit(1)

    print(f"\n{B}발행 팝오버 셀렉터 디버그{X}")
    print(f"  URL     : {WRITE_URL}")
    print(f"  세션    : {SESSION}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, slow_mo=200)
        ctx_kw: dict = {"locale": "ko-KR", "timezone_id": "Asia/Seoul"}
        if Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
        ctx  = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        # ── 1. 에디터 열기 ──────────────────────────────────────────────────
        _section("에디터 오픈")
        print(f"  {Y}→ {WRITE_URL}{X}")
        page.goto(WRITE_URL)
        page.wait_for_load_state("domcontentloaded", timeout=20_000)
        time.sleep(2)
        print(f"  현재 URL: {page.url}")

        if "login" in page.url or "nid.naver.com" in page.url:
            print(f"  {R}로그인 필요. session_state.json 또는 .env 자격증명을 확인하세요.{X}")
            browser.close()
            sys.exit(1)

        # ── 2. 팝오버 열기 전 DOM 스냅샷 (baseline) ────────────────────────
        _section("팝오버 오픈 전 — radio 요소 기준값")
        _probe_context("page (before)", page)

        # ── 3. 발행 버튼 클릭 ───────────────────────────────────────────────
        _section("발행 버튼 클릭")
        opened = _open_popover(page)

        if not opened:
            print(f"\n  {R}발행 팝오버를 열지 못했습니다. 브라우저를 직접 조작해")
            print(f"  팝오버가 열린 상태로 두고 Enter를 누르세요.{X}")
            try:
                input("  [Enter 후 분석 계속] ")
            except (EOFError, KeyboardInterrupt):
                browser.close()
                return

        # ── 4. 팝오버 열린 뒤 전수 탐색 ────────────────────────────────────
        _section("팝오버 오픈 후 — page 레벨 JS 탐색")
        _probe_context("page (after popover)", page)

        _probe_all_frames(page)

        # ── 5. Playwright 로케이터 직접 시도 ─────────────────────────────────
        _probe_playwright_locators(page)

        # ── 6. 요약 ─────────────────────────────────────────────────────────
        _print_summary(page)

        # ── 7. 브라우저 유지 (수동 확인) ────────────────────────────────────
        print(f"\n{B}브라우저를 직접 확인하세요.{X}")
        print(f"  팝오버가 열려 있는 상태에서 DevTools → Elements 탭으로")
        print(f"  '현재' / '예약' 요소의 실제 HTML 구조를 확인하면 더 정확합니다.")
        try:
            input(f"\n  {D}[Enter] 종료{X} ")
        except (EOFError, KeyboardInterrupt):
            pass

        browser.close()

    print(f"\n{G}{B}완료{X}")


if __name__ == "__main__":
    main()
