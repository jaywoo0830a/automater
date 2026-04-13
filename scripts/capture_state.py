"""
scripts/capture_state.py
--------------------------
발행 팝오버의 캘린더/시간 위젯 상태를 진단하는 스크립트.

날짜는 <select>가 아닌 캘린더 위젯이므로,
React fiber tree를 탐색하여 실제 상태 구조를 파악한다.

사용법
------
    python scripts/capture_state.py                           # 전체 덤프
    python scripts/capture_state.py --set "2026-04-20 17:30"  # 설정 + 검증
    python scripts/capture_state.py --json                    # JSON 출력
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
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

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"


# ---------------------------------------------------------------------------
# JS: 캘린더 위젯 구조 탐색
# ---------------------------------------------------------------------------
_CALENDAR_DUMP_JS = """() => {
    const result = {header: null, navButtons: [], dayCells: [], dateDisplay: null};

    // 1. 캘린더 헤더 ("YYYY년 M월")
    for (const el of document.querySelectorAll('strong, span, div, p, h1, h2, h3, h4')) {
        const text = el.textContent.trim();
        const m = text.match(/^(\\d{4})년\\s*(\\d{1,2})월$/);
        if (m) {
            result.header = {
                tag: el.tagName,
                text: text,
                year: parseInt(m[1]),
                month: parseInt(m[2]),
                className: el.className || '',
                parentTag: el.parentElement?.tagName || '',
                parentClass: el.parentElement?.className || '',
            };
            // 헤더 주변 버튼 (네비게이션 화살표)
            const parent = el.parentElement;
            if (parent) {
                const btns = [...parent.querySelectorAll('button, a[role="button"]')];
                const hRect = el.getBoundingClientRect();
                result.navButtons = btns.map(btn => {
                    const bRect = btn.getBoundingClientRect();
                    return {
                        tag: btn.tagName,
                        text: btn.textContent.trim().slice(0, 20),
                        className: btn.className || '',
                        ariaLabel: btn.getAttribute('aria-label') || '',
                        position: bRect.right < hRect.left + 5 ? 'prev'
                                : bRect.left > hRect.right - 5 ? 'next'
                                : 'unknown',
                        rect: {left: bRect.left, right: bRect.right},
                    };
                });
            }
            break;
        }
    }

    // 2. 날짜 표시 ("2026. 04. 22" 패턴)
    for (const el of document.querySelectorAll('*')) {
        const text = el.textContent.trim();
        if (/^\\d{4}\\.\\s*\\d{2}\\.\\s*\\d{2}$/.test(text) && el.children.length <= 1) {
            result.dateDisplay = {
                tag: el.tagName,
                text: text,
                className: el.className || '',
                parentClass: el.parentElement?.className || '',
            };
            break;
        }
    }

    // 3. 캘린더 그리드 셀 (요일 텍스트와 숫자 셀)
    const tables = document.querySelectorAll('table');
    for (const table of tables) {
        const cells = [...table.querySelectorAll('td, th')];
        if (cells.length >= 28) {  // 7 days * 4+ weeks
            result.dayCells = cells.slice(0, 42).map(cell => ({
                tag: cell.tagName,
                text: cell.textContent.trim(),
                className: cell.className || '',
                hasButton: cell.querySelector('button') !== null,
                buttonClass: cell.querySelector('button')?.className || '',
                isToday: cell.className.includes('today') ||
                         cell.querySelector('.today, [class*=today]') !== null,
                isSelected: cell.className.includes('selected') ||
                            cell.querySelector('.selected, [class*=selected]') !== null,
            }));
            break;
        }
    }

    // table이 없으면 div 기반 그리드 탐색
    if (result.dayCells.length === 0) {
        // role="grid" 또는 aria-label에 캘린더 관련 텍스트가 있는 요소
        const grids = document.querySelectorAll('[role="grid"], [role="table"]');
        for (const grid of grids) {
            const cells = [...grid.querySelectorAll('[role="gridcell"], [role="cell"], button, a')];
            if (cells.length >= 28) {
                result.dayCells = cells.slice(0, 42).map(cell => ({
                    tag: cell.tagName,
                    text: cell.textContent.trim(),
                    className: cell.className || '',
                    role: cell.getAttribute('role') || '',
                }));
                break;
            }
        }
    }

    // 여전히 없으면: "2026년 4월" 헤더 근처의 숫자 요소들
    if (result.dayCells.length === 0 && result.header) {
        // 헤더의 가장 가까운 컨테이너에서 숫자 텍스트 요소 수집
        let container = result.header.tag ? null : null;
        // walk up to find a reasonably large container
        const headerEl = [...document.querySelectorAll('*')].find(el =>
            el.textContent.trim().match(/^\\d{4}년\\s*\\d{1,2}월$/)
            && el.children.length <= 3
        );
        if (headerEl) {
            let parent = headerEl.parentElement;
            for (let i = 0; i < 5 && parent; i++) {
                const nums = [...parent.querySelectorAll('*')].filter(el => {
                    const t = el.textContent.trim();
                    return /^\\d{1,2}$/.test(t) && el.children.length === 0
                           && parseInt(t) >= 1 && parseInt(t) <= 31;
                });
                if (nums.length >= 20) {
                    result.dayCells = nums.map(el => ({
                        tag: el.tagName,
                        text: el.textContent.trim(),
                        className: el.className || '',
                        parentTag: el.parentElement?.tagName || '',
                        parentClass: (el.parentElement?.className || '').slice(0, 40),
                        clickable: el.tagName === 'BUTTON' || el.tagName === 'A'
                                   || el.getAttribute('role') === 'button'
                                   || !!el.onclick,
                        rect: (() => {
                            const r = el.getBoundingClientRect();
                            return {top: Math.round(r.top), left: Math.round(r.left),
                                    w: Math.round(r.width), h: Math.round(r.height)};
                        })(),
                    }));
                    break;
                }
                parent = parent.parentElement;
            }
        }
    }

    return result;
}"""

# ---------------------------------------------------------------------------
# JS: 캘린더 React fiber 탐색
# ---------------------------------------------------------------------------
_CALENDAR_REACT_JS = """() => {
    // "YYYY년 M월" 헤더 요소에서 시작하여 fiber tree를 위로 올라간다
    let headerEl = null;
    for (const el of document.querySelectorAll('*')) {
        const text = el.textContent.trim();
        if (/^\\d{4}년\\s*\\d{1,2}월$/.test(text) && el.children.length <= 3) {
            headerEl = el;
            break;
        }
    }
    if (!headerEl) return {error: 'calendar header element not found'};

    const fiberKey = Object.keys(headerEl).find(k =>
        k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance')
    );
    if (!fiberKey) return {error: 'no React fiber on header element', tag: headerEl.tagName};

    // Walk up the fiber tree, collecting component info
    const components = [];
    let fiber = headerEl[fiberKey];
    for (let depth = 0; depth < 30 && fiber; depth++) {
        const entry = {depth, type: null, hasState: false, props: null, stateKeys: null};

        // Component name
        if (typeof fiber.type === 'function') {
            entry.type = fiber.type.name || fiber.type.displayName || '(anonymous fn)';
        } else if (typeof fiber.type === 'string') {
            entry.type = fiber.type;  // HTML element
        } else {
            entry.type = String(fiber.type);
        }

        // Props (safe extract)
        if (fiber.memoizedProps) {
            try {
                const keys = Object.keys(fiber.memoizedProps);
                entry.props = {};
                for (const k of keys.slice(0, 15)) {
                    const v = fiber.memoizedProps[k];
                    const t = typeof v;
                    if (t === 'string' || t === 'number' || t === 'boolean' || v === null) {
                        entry.props[k] = v;
                    } else if (t === 'function') {
                        entry.props[k] = '(function)';
                    } else if (v instanceof Date) {
                        entry.props[k] = v.toISOString();
                    } else if (Array.isArray(v)) {
                        entry.props[k] = `Array(${v.length})`;
                    } else if (t === 'object') {
                        // Look for date-like properties
                        const objKeys = Object.keys(v).slice(0, 5);
                        const dateKeys = objKeys.filter(ok =>
                            /year|month|day|date|time|hour|min/i.test(ok)
                        );
                        if (dateKeys.length > 0) {
                            const dateObj = {};
                            for (const dk of dateKeys) {
                                dateObj[dk] = v[dk];
                            }
                            entry.props[k] = dateObj;
                        } else {
                            entry.props[k] = '{' + objKeys.join(', ') + '}';
                        }
                    }
                }
            } catch (e) {
                entry.props = {error: e.message};
            }
        }

        // State (hooks: memoizedState is a linked list)
        if (fiber.memoizedState) {
            entry.hasState = true;
            try {
                let state = fiber.memoizedState;
                const stateItems = [];
                for (let si = 0; si < 10 && state; si++) {
                    const val = state.memoizedState;
                    const t = typeof val;
                    if (val === null || val === undefined) {
                        stateItems.push(null);
                    } else if (t === 'string' || t === 'number' || t === 'boolean') {
                        stateItems.push(val);
                    } else if (val instanceof Date) {
                        stateItems.push(val.toISOString());
                    } else if (Array.isArray(val)) {
                        stateItems.push(`Array(${val.length})`);
                    } else if (t === 'object') {
                        const keys = Object.keys(val).slice(0, 8);
                        const summary = {};
                        for (const k of keys) {
                            const sv = val[k];
                            if (sv instanceof Date) summary[k] = sv.toISOString();
                            else if (typeof sv === 'object' && sv !== null)
                                summary[k] = '{...}';
                            else summary[k] = sv;
                        }
                        stateItems.push(summary);
                    } else if (t === 'function') {
                        stateItems.push('(fn)');
                    } else {
                        stateItems.push(`(${t})`);
                    }
                    state = state.next;
                }
                entry.stateKeys = stateItems;
            } catch (e) {
                entry.stateKeys = ['error: ' + e.message];
            }
        }

        // Only include interesting entries (components with state or date-related props)
        if (entry.hasState || (entry.props && typeof fiber.type === 'function')) {
            components.push(entry);
        }

        fiber = fiber.return;
    }
    return {fiberKey, headerText: headerEl.textContent.trim(), components};
}"""

# ---------------------------------------------------------------------------
# JS: "2026. 04. 22" 날짜 표시 영역에서 React fiber 탐색
# ---------------------------------------------------------------------------
_DATE_DISPLAY_REACT_JS = """() => {
    // "YYYY. MM. DD" 표시 요소 찾기
    let dateEl = null;
    for (const el of document.querySelectorAll('*')) {
        const text = el.textContent.trim();
        if (/^\\d{4}\\.\\s*\\d{2}\\.\\s*\\d{2}$/.test(text) && el.children.length <= 1) {
            dateEl = el;
            break;
        }
    }
    // fallback: 좀 더 넓은 패턴
    if (!dateEl) {
        for (const el of document.querySelectorAll('*')) {
            const text = el.textContent.trim();
            if (/\\d{4}\\.\\s*\\d{2}\\.\\s*\\d{2}/.test(text) && el.children.length <= 3) {
                dateEl = el;
                break;
            }
        }
    }
    if (!dateEl) return {error: 'date display not found'};

    const fiberKey = Object.keys(dateEl).find(k =>
        k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance')
    );
    if (!fiberKey) return {error: 'no fiber', tag: dateEl.tagName, text: dateEl.textContent.trim()};

    // fiber tree 탐색 (캘린더 헤더와 동일한 로직)
    const components = [];
    let fiber = dateEl[fiberKey];
    for (let depth = 0; depth < 30 && fiber; depth++) {
        if (typeof fiber.type !== 'function') { fiber = fiber.return; continue; }

        const name = fiber.type.name || fiber.type.displayName || '(anon)';
        const entry = {depth, name, props: {}, state: []};

        // Props
        if (fiber.memoizedProps) {
            for (const [k, v] of Object.entries(fiber.memoizedProps).slice(0, 12)) {
                const t = typeof v;
                if (v instanceof Date) entry.props[k] = v.toISOString();
                else if (t === 'function') entry.props[k] = '(fn)';
                else if (t === 'object' && v !== null) {
                    const keys = Object.keys(v);
                    if (keys.length <= 6)
                        entry.props[k] = JSON.parse(JSON.stringify(v, (_, val) =>
                            val instanceof Date ? val.toISOString() :
                            typeof val === 'function' ? '(fn)' : val
                        ));
                    else
                        entry.props[k] = `{${keys.slice(0,4).join(', ')}...}`;
                }
                else entry.props[k] = v;
            }
        }

        // State (hooks linked list)
        if (fiber.memoizedState) {
            let s = fiber.memoizedState;
            for (let i = 0; i < 8 && s; i++) {
                const val = s.memoizedState;
                try {
                    if (val === null || val === undefined) entry.state.push(null);
                    else if (typeof val === 'object' && !(val instanceof Date)) {
                        entry.state.push(JSON.parse(JSON.stringify(val, (_, v) =>
                            v instanceof Date ? v.toISOString() :
                            typeof v === 'function' ? '(fn)' : v
                        )));
                    }
                    else entry.state.push(val);
                } catch { entry.state.push('(circular)'); }
                s = s.next;
            }
        }

        components.push(entry);
        fiber = fiber.return;
    }
    return {dateText: dateEl.textContent.trim(), fiberKey, components};
}"""

# ---------------------------------------------------------------------------
# JS: <select> 덤프 (시/분)
# ---------------------------------------------------------------------------
_DUMP_SELECTS_JS = """() => {
    return [...document.querySelectorAll('select')].map((sel, i) => ({
        index: i,
        className: sel.className || '',
        value: sel.value,
        optionCount: [...sel.options].length,
        optionValues: [...sel.options].map(o => o.value),
        parentClass: sel.parentElement?.className || '',
    }));
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def print_section(title: str) -> None:
    print(f"\n{B}{'═' * 60}{X}")
    print(f"{B}  {title}{X}")
    print(f"{B}{'═' * 60}{X}")


def print_calendar_dump(cal: dict) -> None:
    h = cal.get("header")
    if h:
        print(f"\n  {C}캘린더 헤더{X}")
        print(f"    <{h['tag']}> {G}{h['text']!r}{X}  (year={h['year']}, month={h['month']})")
        print(f"    class    : {D}{h['className']}{X}")
        print(f"    부모     : <{h['parentTag']}> class={D}{h['parentClass'][:50]}{X}")
    else:
        print(f"\n  {R}캘린더 헤더를 찾지 못함{X}")

    navs = cal.get("navButtons", [])
    if navs:
        print(f"\n  {C}네비게이션 버튼{X}")
        for btn in navs:
            pos_color = G if btn["position"] in ("prev", "next") else Y
            print(f"    {pos_color}{btn['position']:5s}{X} "
                  f"<{btn['tag']}> text={btn['text']!r} "
                  f"aria={btn['ariaLabel']!r} class={D}{btn['className'][:40]}{X}")
    else:
        print(f"\n  {R}네비게이션 버튼 없음{X}")

    dd = cal.get("dateDisplay")
    if dd:
        print(f"\n  {C}날짜 표시{X}")
        print(f"    <{dd['tag']}> {G}{dd['text']!r}{X}")
        print(f"    class    : {D}{dd['className']}{X}")
        print(f"    부모class: {D}{dd['parentClass'][:50]}{X}")
    else:
        print(f"\n  {Y}날짜 표시 (YYYY. MM. DD) 미발견{X}")

    cells = cal.get("dayCells", [])
    if cells:
        print(f"\n  {C}캘린더 셀{X} ({len(cells)}개)")
        for cell in cells[:42]:
            text = cell.get("text", "")
            if not text or text in ("일","월","화","수","목","금","토"):
                continue
            extras = []
            if cell.get("clickable"):
                extras.append(f"{G}clickable{X}")
            if cell.get("isSelected"):
                extras.append(f"{C}SELECTED{X}")
            if cell.get("isToday"):
                extras.append(f"{Y}today{X}")
            extra_str = f"  [{', '.join(extras)}]" if extras else ""
            rect = cell.get("rect", {})
            rect_str = f"  ({rect.get('left',0)},{rect.get('top',0)} {rect.get('w',0)}x{rect.get('h',0)})" if rect else ""
            print(f"    {text:>3s}  <{cell.get('tag', '?')}>  "
                  f"class={D}{cell.get('className', '')[:30]}{X}  "
                  f"parent=<{cell.get('parentTag', '')}>  "
                  f"pclass={D}{cell.get('parentClass', '')[:25]}{X}"
                  f"{extra_str}{rect_str}")
    else:
        print(f"\n  {R}캘린더 셀을 찾지 못함{X}")


def print_react_tree(data: dict, label: str) -> None:
    if "error" in data:
        print(f"  {R}오류: {data['error']}{X}")
        for k, v in data.items():
            if k != "error":
                print(f"    {k}: {v}")
        return

    print(f"  fiber: {D}{data.get('fiberKey', '?')}{X}")
    source = data.get("headerText") or data.get("dateText", "?")
    print(f"  시작점: {G}{source!r}{X}")

    for comp in data.get("components", []):
        depth = comp.get("depth", 0)
        name = comp.get("type") or comp.get("name", "?")
        indent = "  " + "  " * min(depth // 3, 4)

        print(f"\n{indent}{C}[{depth}] {name}{X}")

        # Props
        props = comp.get("props", {})
        if props:
            for k, v in props.items():
                v_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else repr(v)
                # Highlight date-related keys
                is_date = any(w in k.lower() for w in ("date", "year", "month", "day", "time", "schedule"))
                color = G if is_date else D
                print(f"{indent}  prop.{color}{k}{X} = {v_str[:80]}")

        # State
        state = comp.get("stateKeys") or comp.get("state", [])
        if state:
            for i, s in enumerate(state):
                if s is None:
                    continue
                s_str = json.dumps(s, ensure_ascii=False) if isinstance(s, (dict, list)) else repr(s)
                is_interesting = isinstance(s, dict) or (isinstance(s, (int, str)) and s not in (True, False, '(fn)'))
                color = G if is_interesting else D
                print(f"{indent}  {color}state[{i}]{X} = {s_str[:100]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="발행 팝오버 캘린더 상태 진단")
    parser.add_argument("--set", metavar="DATETIME", help='날짜 설정 (예: "2026-04-20 17:30")')
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    parser.add_argument("--frame-dump", action="store_true", help="iframe 목록 출력")
    args = parser.parse_args()

    if not NAVER_ID or not BLOG_ID:
        print(f"{R}오류: .env에 NAVER_ID, NAVER_BLOG_ID가 필요합니다.{X}")
        sys.exit(1)

    print(f"\n{B}Naver 발행 팝오버 캘린더 진단{X}")
    print(f"  URL  : {WRITE_URL}")
    print(f"  세션 : {SESSION}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx_kw: dict = {"locale": "ko-KR", "timezone_id": "Asia/Seoul"}
        if Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
        else:
            print(f"{R}세션 파일 없음 — bash ./run/test.sh --session 실행 필요{X}")
            sys.exit(1)

        ctx = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        print(f"\n  {Y}→ 에디터 로딩...{X}")
        page.goto(WRITE_URL, timeout=60_000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        if "nid.naver.com" in page.url or "login" in page.url.lower():
            print(f"{R}세션 만료. 재로그인 필요.{X}")
            browser.close()
            sys.exit(1)

        page.frame_locator("#mainFrame").locator(".se-content").wait_for(
            state="visible", timeout=30_000,
        )
        print(f"  {G}→ 에디터 로드 완료{X}")

        if args.frame_dump:
            print_section("Frames")
            for i, frame in enumerate(page.frames):
                print(f"  [{i}] name={frame.name!r}  url={frame.url[:100]}")

        # 발행 버튼
        print(f"\n  {Y}→ 발행 버튼 클릭...{X}")
        publish_btn = page.frame_locator("#mainFrame").locator(
            'button[data-click-area="tpb.publish"]'
        )
        publish_btn.wait_for(state="visible", timeout=10_000)
        publish_btn.click()
        time.sleep(1)

        # PostWriteForm iframe
        js_frame = None
        for frame in page.frames:
            if "PostWriteForm" in frame.url:
                js_frame = frame
                break

        if not js_frame:
            print(f"{R}PostWriteForm iframe 미발견{X}")
            browser.close()
            sys.exit(1)

        print(f"  {G}→ PostWriteForm 발견{X}")

        # 예약 라디오
        print(f"  {Y}→ 예약 라디오 클릭...{X}")
        js_frame.evaluate("""() => {
            const el = document.querySelector('input[name="radio_time"][value="pre"]');
            if (el) el.click();
        }""")
        time.sleep(1.5)

        # ── A. 캘린더 위젯 구조 ──
        print_section("캘린더 위젯 구조")
        cal = js_frame.evaluate(_CALENDAR_DUMP_JS)
        if args.json:
            print(json.dumps(cal, ensure_ascii=False, indent=2))
        else:
            print_calendar_dump(cal)

        # ── B. 캘린더 React Fiber Tree ──
        print_section("캘린더 헤더 → React Fiber Tree")
        react_cal = js_frame.evaluate(_CALENDAR_REACT_JS)
        if args.json:
            print(json.dumps(react_cal, ensure_ascii=False, indent=2))
        else:
            print_react_tree(react_cal, "calendar")

        # ── C. 날짜 표시 → React Fiber Tree ──
        print_section("날짜 표시 → React Fiber Tree")
        react_date = js_frame.evaluate(_DATE_DISPLAY_REACT_JS)
        if args.json:
            print(json.dumps(react_date, ensure_ascii=False, indent=2))
        else:
            print_react_tree(react_date, "dateDisplay")

        # ── D. <select> (시/분) ──
        print_section("SELECT (시/분)")
        selects = js_frame.evaluate(_DUMP_SELECTS_JS)
        if args.json:
            print(json.dumps(selects, ensure_ascii=False, indent=2))
        else:
            for sel in selects:
                vals = sel["optionValues"]
                sample = vals[:5]
                print(f"  [{sel['index']}] class={D}{sel['className'][:40]}{X}  "
                      f"value={G}{sel['value']!r}{X}  "
                      f"options={sel['optionCount']}개  {sample}{'...' if len(vals) > 5 else ''}")

        # ── --set: 설정 테스트 ──
        if args.set:
            try:
                target = datetime.strptime(args.set, "%Y-%m-%d %H:%M")
            except ValueError:
                print(f"\n{R}날짜 형식 오류: {args.set!r}  (예: '2026-04-20 17:30'){X}")
                browser.close()
                sys.exit(1)

            print_section(f"설정 테스트: {target.strftime('%Y-%m-%d %H:%M')}")
            print(f"  (TODO: React state 구조 확인 후 구현)")
            print(f"  위 Fiber Tree 출력에서 날짜 관련 state/prop을 찾아주세요.")

        # 대기
        print(f"\n  {D}엔터를 누르면 종료합니다.{X}")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass

        browser.close()

    print(f"\n{G}{B}완료{X}")


if __name__ == "__main__":
    main()
