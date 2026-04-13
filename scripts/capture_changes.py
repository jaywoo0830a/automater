"""
scripts/capture_changes.py
-----------------------------
브라우저에서 일어나는 모든 변화를 실시간 추적하는 진단 스크립트.

캘린더를 클릭하든, 드롭다운을 바꾸든, 어떤 조작이든
DOM / input / network / React state 변화를 전부 캡처한다.

사용법
------
    python scripts/capture_changes.py              # 기본 — 에디터 열기 → 발행 팝오버 → 추적 시작
    python scripts/capture_changes.py --url URL    # 커스텀 URL
    python scripts/capture_changes.py --no-popover # 발행 팝오버 열지 않음
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright, Page

NAVER_ID  = os.getenv("NAVER_ID", "")
BLOG_ID   = os.getenv("NAVER_BLOG_ID", "")
SESSION   = os.getenv("SESSION_PATH", f"{NAVER_ID}_session.json")
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

# ---------------------------------------------------------------------------
# JS: 변화 추적기 설치 — 모든 프레임에 주입
# ---------------------------------------------------------------------------
_TRACKER_JS = """() => {
    if (window.__changeTracker) return 'already installed';
    window.__changeTracker = true;

    // 최상위 윈도우에 변경 큐 생성
    if (!window.top.__changeQueue) window.top.__changeQueue = [];
    const Q = window.top.__changeQueue;
    const FRAME = window === window.top ? 'top' : (window.name || window.location.href.split('/').pop().split('?')[0] || 'iframe');
    const MAX = 500;

    function push(entry) {
        entry.frame = FRAME;
        entry.time = new Date().toISOString().slice(11, 23);
        if (Q.length < MAX) Q.push(entry);
    }

    // ── 1. input / select / textarea 값 변경 ──
    document.addEventListener('change', (e) => {
        const el = e.target;
        const tag = el.tagName?.toLowerCase();
        if (!tag) return;
        push({
            type: 'value_change',
            tag: tag,
            name: el.name || '',
            id: el.id || '',
            className: (el.className || '').slice(0, 60),
            value: el.value,
            checked: el.checked ?? null,
            inputType: el.type || '',
        });
    }, true);

    // ── 2. 클릭 추적 (실제 클릭, capture_selectors와 달리 차단 안 함) ──
    document.addEventListener('click', (e) => {
        const el = e.target;
        // interactive 요소로 snap
        let node = el;
        const TAGS = new Set(['button','a','input','select','label','td','th']);
        for (let i = 0; i < 5 && node && node !== document.body; i++) {
            if (TAGS.has(node.tagName?.toLowerCase()) || node.getAttribute('role')) break;
            node = node.parentElement;
        }
        if (!node) node = el;
        push({
            type: 'click',
            tag: node.tagName?.toLowerCase(),
            text: (node.textContent || '').trim().slice(0, 50),
            className: (node.className || '').slice(0, 60),
            role: node.getAttribute('role') || '',
            ariaLabel: node.getAttribute('aria-label') || '',
            id: node.id || '',
        });
    }, true);

    // ── 3. DOM Mutation Observer ──
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.type === 'attributes') {
                const el = m.target;
                const tag = el.tagName?.toLowerCase();
                const attr = m.attributeName;
                // class 변경은 너무 많으므로 주요 속성만
                if (['value', 'checked', 'disabled', 'hidden', 'aria-selected',
                     'aria-checked', 'data-selected', 'data-date', 'data-value',
                     'style'].includes(attr)) {
                    push({
                        type: 'attr_change',
                        tag: tag,
                        attr: attr,
                        newValue: (el.getAttribute(attr) || '').slice(0, 100),
                        className: (el.className || '').slice(0, 40),
                        text: (el.textContent || '').trim().slice(0, 30),
                        id: el.id || '',
                    });
                }
                // class 변경 중 selected/active 관련만
                if (attr === 'class') {
                    const cls = el.className || '';
                    if (/select|active|current|today|chosen|highlight/i.test(cls)) {
                        push({
                            type: 'class_change',
                            tag: tag,
                            className: cls.slice(0, 80),
                            text: (el.textContent || '').trim().slice(0, 30),
                        });
                    }
                }
            }
            // 자식 노드 추가/제거 (캘린더 리렌더링 감지)
            if (m.type === 'childList' && (m.addedNodes.length || m.removedNodes.length)) {
                const parent = m.target;
                const tag = parent.tagName?.toLowerCase();
                const added = m.addedNodes.length;
                const removed = m.removedNodes.length;
                // 의미 있는 변경만 (텍스트 노드 제외, 최소 1개 element)
                const hasElement = [...m.addedNodes, ...m.removedNodes].some(
                    n => n.nodeType === 1
                );
                if (hasElement) {
                    push({
                        type: 'dom_change',
                        tag: tag,
                        className: (parent.className || '').slice(0, 60),
                        added: added,
                        removed: removed,
                        childCount: parent.children.length,
                        // 추가된 첫 element의 정보
                        firstAdded: (() => {
                            for (const n of m.addedNodes) {
                                if (n.nodeType === 1) return {
                                    tag: n.tagName?.toLowerCase(),
                                    text: (n.textContent || '').trim().slice(0, 40),
                                    className: (n.className || '').slice(0, 40),
                                };
                            }
                            return null;
                        })(),
                    });
                }
            }
        }
    });

    observer.observe(document.body, {
        attributes: true,
        childList: true,
        subtree: true,
        attributeOldValue: false,
    });

    // ── 4. React state 변경 감지 (select 요소) ──
    // select의 value를 주기적으로 폴링
    const selects = [...document.querySelectorAll('select')];
    const selectValues = {};
    selects.forEach((sel, i) => { selectValues[i] = sel.value; });

    setInterval(() => {
        selects.forEach((sel, i) => {
            if (sel.value !== selectValues[i]) {
                push({
                    type: 'select_poll',
                    index: i,
                    className: (sel.className || '').slice(0, 40),
                    oldValue: selectValues[i],
                    newValue: sel.value,
                });
                selectValues[i] = sel.value;
            }
        });
    }, 200);

    return 'installed in ' + FRAME;
}"""

# ---------------------------------------------------------------------------
# JS: 변경 큐 비우기
# ---------------------------------------------------------------------------
_DRAIN_JS = """() => {
    if (!window.__changeQueue || !window.__changeQueue.length) return [];
    return window.__changeQueue.splice(0);
}"""

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
_TYPE_COLORS = {
    "click": C,
    "value_change": G,
    "attr_change": Y,
    "class_change": Y,
    "dom_change": D,
    "select_poll": G,
}

_TYPE_ICONS = {
    "click": "🖱",
    "value_change": "📝",
    "attr_change": "🔧",
    "class_change": "🎨",
    "dom_change": "🌿",
    "select_poll": "📊",
}


def format_entry(entry: dict) -> str:
    t = entry.get("type", "?")
    color = _TYPE_COLORS.get(t, D)
    icon = _TYPE_ICONS.get(t, "?")
    time_str = entry.get("time", "")
    frame = entry.get("frame", "?")

    parts = [f"  {D}{time_str}{X} {icon} {color}{t:14s}{X} {D}[{frame}]{X}"]

    if t == "click":
        text = entry.get("text", "")
        tag = entry.get("tag", "")
        cls = entry.get("className", "")
        role = entry.get("role", "")
        info = f"<{tag}>"
        if text:
            info += f' "{text}"'
        if role:
            info += f" role={role}"
        if cls:
            info += f" {D}class={cls[:40]}{X}"
        parts.append(f"    {info}")

    elif t == "value_change":
        tag = entry.get("tag", "")
        name = entry.get("name", "")
        val = entry.get("value", "")
        checked = entry.get("checked")
        cls = entry.get("className", "")
        info = f"<{tag}>"
        if name:
            info += f" name={name!r}"
        info += f" → {G}{val!r}{X}"
        if checked is not None:
            info += f" checked={checked}"
        if cls:
            info += f" {D}{cls[:30]}{X}"
        parts.append(f"    {info}")

    elif t == "attr_change":
        attr = entry.get("attr", "")
        val = entry.get("newValue", "")
        text = entry.get("text", "")
        tag = entry.get("tag", "")
        info = f"<{tag}> {Y}{attr}{X}={val!r}"
        if text:
            info += f' "{text}"'
        parts.append(f"    {info}")

    elif t == "class_change":
        cls = entry.get("className", "")
        text = entry.get("text", "")
        tag = entry.get("tag", "")
        parts.append(f"    <{tag}> {Y}{cls[:60]}{X} \"{text}\"")

    elif t == "dom_change":
        added = entry.get("added", 0)
        removed = entry.get("removed", 0)
        tag = entry.get("tag", "")
        cls = entry.get("className", "")
        first = entry.get("firstAdded")
        info = f"<{tag}> +{added}/-{removed} children"
        if cls:
            info += f" {D}{cls[:30]}{X}"
        if first:
            info += f"\n      첫 추가: <{first.get('tag', '?')}> \"{first.get('text', '')[:30]}\" {D}{first.get('className', '')[:30]}{X}"
        parts.append(f"    {info}")

    elif t == "select_poll":
        old = entry.get("oldValue", "")
        new = entry.get("newValue", "")
        cls = entry.get("className", "")
        parts.append(f"    select[{entry.get('index', '?')}] {old!r} → {G}{new!r}{X} {D}{cls[:30]}{X}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="브라우저 변화 실시간 추적")
    parser.add_argument("--url", default=WRITE_URL)
    parser.add_argument("--no-popover", action="store_true", help="발행 팝오버 열지 않음")
    parser.add_argument("--json", action="store_true", help="JSON raw 출력")
    args = parser.parse_args()

    if not NAVER_ID or not BLOG_ID:
        print(f"{R}오류: .env에 NAVER_ID, NAVER_BLOG_ID가 필요합니다.{X}")
        sys.exit(1)

    print(f"\n{B}Naver 변화 추적기{X}")
    print(f"  URL  : {args.url}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx_kw: dict = {"locale": "ko-KR", "timezone_id": "Asia/Seoul"}
        if Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
        else:
            print(f"{R}세션 없음 — bash ./run/test.sh --session{X}")
            sys.exit(1)

        ctx = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        print(f"\n  {Y}→ 페이지 로딩...{X}")
        page.goto(args.url, timeout=60_000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)

        if "nid.naver.com" in page.url or "login" in page.url.lower():
            print(f"{R}세션 만료{X}")
            browser.close()
            sys.exit(1)

        page.frame_locator("#mainFrame").locator(".se-content").wait_for(
            state="visible", timeout=30_000,
        )
        print(f"  {G}→ 에디터 로드 완료{X}")

        if not args.no_popover:
            print(f"  {Y}→ 발행 팝오버 열기...{X}")
            publish_btn = page.frame_locator("#mainFrame").locator(
                'button[data-click-area="tpb.publish"]'
            )
            publish_btn.wait_for(state="visible", timeout=10_000)
            publish_btn.click()
            time.sleep(1)

            # 예약 라디오
            for frame in page.frames:
                if "PostWriteForm" in frame.url:
                    frame.evaluate("""() => {
                        const el = document.querySelector('input[name="radio_time"][value="pre"]');
                        if (el) el.click();
                    }""")
                    break
            time.sleep(1)

        # ── 모든 프레임에 추적기 설치 ──
        print(f"\n  {Y}→ 추적기 설치 중...{X}")
        installed = []
        for frame in page.frames:
            try:
                result = frame.evaluate(_TRACKER_JS)
                installed.append(f"{frame.url.split('/')[-1].split('?')[0] or 'main'}: {result}")
            except Exception as e:
                pass

        for i in installed:
            print(f"    {G}✓{X} {i}")

        # 새 프레임에 자동 설치
        def on_frame(frame):
            time.sleep(0.3)
            try:
                frame.evaluate(_TRACKER_JS)
            except Exception:
                pass

        page.on("frameattached", on_frame)
        page.on("framenavigated", lambda f: on_frame(f) if f != page.main_frame else None)

        # ── 추적 루프 ──
        print(f"\n{B}{'═' * 60}{X}")
        print(f"  {B}추적 시작{X} — 브라우저에서 조작하세요")
        print(f"  캘린더 날짜 클릭, 드롭다운 변경 등 모든 변화가 여기 표시됩니다.")
        print(f"  {D}Ctrl+C 로 종료{X}")
        print(f"{B}{'═' * 60}{X}\n")

        event_count = 0
        try:
            while True:
                try:
                    events = page.evaluate(_DRAIN_JS) or []
                except Exception:
                    events = []

                for entry in events:
                    event_count += 1

                    if args.json:
                        print(json.dumps(entry, ensure_ascii=False))
                    else:
                        print(format_entry(entry))

                time.sleep(0.15)

                # 브라우저 살아있는지 확인
                try:
                    page.title()
                except Exception:
                    print(f"\n  {Y}브라우저 닫힘{X}")
                    break

        except KeyboardInterrupt:
            pass

        print(f"\n  {D}총 {event_count}개 이벤트 캡처{X}")
        browser.close()

    print(f"\n{G}{B}완료{X}")


if __name__ == "__main__":
    main()
