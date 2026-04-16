"""
scripts/capture_selectors.py
------------------------------
브라우저에서 요소를 직접 클릭하면, 그 요소의 가장 안정적인 셀렉터를
자동으로 분석해서 selectors/naver/editor.yaml (또는 login.yaml)에 저장합니다.

원칙
----
- 클래스명, ID, XPath는 빌드마다 바뀔 수 있으므로 최후 수단으로만 사용
- role+name > label > text > testid > placeholder > css 순으로 안정성 판단
- expose_function 대신 JS 전역 변수 폴링 방식 사용 (데드락 방지)

사용법
------
    # 에디터(글쓰기) 페이지 캡처 — 기본
    python scripts/capture_selectors.py
    python scripts/capture_selectors.py --merge

    # 로그인 창 캡처 (세션 무시하고 로그인 페이지 노출)
    python scripts/capture_selectors.py --mode login
    python scripts/capture_selectors.py --mode login --merge
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright, Page

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
NAVER_ID  = os.getenv("NAVER_ID",      "")
NAVER_PW  = os.getenv("NAVER_PW",      "")
BLOG_ID   = os.getenv("NAVER_BLOG_ID", "")
SESSION   = os.getenv("SESSION_PATH",  f"{NAVER_ID}_session.json")
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&"
LOGIN_URL = "https://nid.naver.com/nidlogin.login"

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
G="\033[92m"; R="\033[91m"; Y="\033[93m"
C="\033[96m"; B="\033[1m";  D="\033[2m"; X="\033[0m"

# ---------------------------------------------------------------------------
# Stability ranking (낮을수록 안정적)
# ---------------------------------------------------------------------------
STABILITY: dict[str, int] = {
    "role+name":   1,
    "label":       2,
    "text":        3,
    "testid":      4,
    "placeholder": 5,
    "alt":         6,
    "css_stable":  7,
    "css":         8,
}

# ---------------------------------------------------------------------------
# JS: 클릭 리스너 — 결과를 window.__captureQueue 에 push (await 없음)
# ---------------------------------------------------------------------------
_LISTENER_JS = """() => {
    if (window.__captureActive) return;
    window.__captureActive = true;

    // Queue lives on the top-level window so all frames can reach it
    if (!window.top.__captureQueue) window.top.__captureQueue = [];

    const isNonce = c =>
        /[a-zA-Z][0-9]{2,}|[0-9]{2,}[a-zA-Z]|__[a-zA-Z0-9]{4,}/.test(c);

    const INTERACTIVE = new Set([
        'button','a','input','select','textarea',
        'label','summary','details',
    ]);

    const findInteractive = (el) => {
        // Walk up the DOM to find the nearest interactive ancestor
        let node = el;
        while (node && node !== document.body) {
            const tag = node.tagName.toLowerCase();
            if (INTERACTIVE.has(tag)) return node;
            // Also treat elements with explicit role
            const role = node.getAttribute('role');
            if (role && ['button','link','checkbox','radio','menuitem',
                          'tab','option','switch','textbox'].includes(role))
                return node;
            node = node.parentElement;
        }
        return el; // fallback: original target
    };

    document.addEventListener('click', (e) => {
        // Ctrl+Click: pass through to real action (do not block)
        if (e.ctrlKey) return;

        // Normal click: capture only, block real action
        e.preventDefault();
        e.stopPropagation();

        // Snap to nearest interactive element
        const el = findInteractive(e.target);

        // Highlight — green for capture-only
        ['__cap_hl'].forEach(id => {
            const old = document.getElementById(id);
            if (old) old.remove();
        });
        const rect = el.getBoundingClientRect();
        const hl = document.createElement('div');
        hl.id = '__cap_hl';
        hl.style.cssText = [
            'position:fixed',
            'top:'    + rect.top    + 'px',
            'left:'   + rect.left   + 'px',
            'width:'  + rect.width  + 'px',
            'height:' + rect.height + 'px',
            'border:2px solid #00ff88',
            'background:rgba(0,255,136,.15)',
            'z-index:999998',
            'pointer-events:none',
            'border-radius:3px',
        ].join(';');
        document.body.appendChild(hl);
        setTimeout(() => hl.remove(), 1500);

        const stable = [...el.classList].filter(c => !isNonce(c));

        // Push to queue — no await, no blocking
        window.top.__captureQueue.push({
            tag:          el.tagName.toLowerCase(),
            role:         el.getAttribute('role') || '',
            ariaLabel:    el.getAttribute('aria-label') || '',
            ariaLabelledBy: (() => {
                const id = el.getAttribute('aria-labelledby');
                if (!id) return '';
                const ref = document.getElementById(id);
                return ref ? (ref.textContent||'').trim().slice(0,60) : '';
            })(),
            testId:       el.getAttribute('data-testid') || '',
            placeholder:  el.getAttribute('placeholder') || '',
            alt:          el.getAttribute('alt') || '',
            forLabel:     (() => {
                if (!el.id) return '';
                const lbl = document.querySelector('label[for="'+el.id+'"]');
                return lbl ? (lbl.textContent||'').trim().slice(0,60) : '';
            })(),
            text:         (el.innerText||el.textContent||'').trim()
                              .split('\\n')[0].slice(0,60),
            allClasses:   [...el.classList].join(' '),
            stableClasses: stable.join(' '),
            cssSelector:  stable.length
                ? el.tagName.toLowerCase()+'.'+stable.join('.')
                : el.tagName.toLowerCase(),
            ancestorCtx:  (() => {
                let n = el.parentElement;
                for (let i=0; i<5&&n; i++,n=n.parentElement) {
                    const t=n.tagName.toLowerCase();
                    const r=n.getAttribute('role');
                    if (['nav','header','footer','main','aside','dialog','form'].includes(t))
                        return t;
                    if (r&&['dialog','navigation','main','banner'].includes(r))
                        return r;
                }
                return '';
            })(),
            id:           el.id || '',
            inputType:    el.getAttribute('type') || '',
            inIframe:     window !== window.top,
        });
    }, true);
}"""

_OVERLAY_JS = """() => {
    const old = document.getElementById('__cap_overlay');
    if (old) old.remove();
    const div = document.createElement('div');
    div.id = '__cap_overlay';
    div.style.cssText = [
        'position:fixed',
        'bottom:12px',
        'left:50%',
        'transform:translateX(-50%)',
        'z-index:999999',
        'background:rgba(0,0,0,.85)',
        'color:#fff',
        'padding:8px 20px',
        'border-radius:20px',
        'font:13px/1.5 monospace',
        'pointer-events:none',
        'box-shadow:0 2px 12px rgba(0,0,0,.4)',
    ].join(';');
    div.textContent = '🎯 클릭 = 캡처   Ctrl+클릭 = 실제 동작';
    document.body.appendChild(div);
}"""

# ---------------------------------------------------------------------------
# Poll: JS 큐에서 클릭 데이터 꺼내기
# page.evaluate()는 CDP 이벤트를 처리하므로 데드락 없음
# ---------------------------------------------------------------------------
def _poll(page: Page) -> list[dict]:
    """Drain the JS capture queue and return items."""
    try:
        return page.evaluate("""() => {
            if (!window.__captureQueue || !window.__captureQueue.length)
                return [];
            const items = window.__captureQueue.splice(0);
            return items;
        }""") or []
    except Exception:
        return []

# ---------------------------------------------------------------------------
# Inject into all frames + re-inject on new frames
# ---------------------------------------------------------------------------
def _inject_all(page: Page) -> None:
    """Inject listener into main page and every sub-frame."""
    # Initialize queue on top window
    try:
        page.evaluate("() => { if(!window.__captureQueue) window.__captureQueue=[]; }")
    except Exception:
        pass
    # Overlay on main page only
    try:
        page.evaluate(_OVERLAY_JS)
    except Exception:
        pass
    # Listener in every frame
    for frame in page.frames:
        try:
            frame.evaluate(_LISTENER_JS)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Stability analysis
# ---------------------------------------------------------------------------
def analyze(data: dict) -> list[dict]:
    candidates: list[dict] = []
    tag = data.get("tag", "")

    # 1. role + name
    role_name = (
        data.get("ariaLabel") or
        data.get("ariaLabelledBy") or
        data.get("text", "")
    ).strip()

    semantic_role = data.get("role", "") or tag
    if tag == "button":   semantic_role = "button"
    elif tag == "a":      semantic_role = "link"
    elif tag in ("input", "textarea"):
        semantic_role = {
            "checkbox": "checkbox", "radio": "radio",
            "submit": "button",     "button": "button",
        }.get(data.get("inputType",""), "textbox")

    if semantic_role and role_name and len(role_name) <= 40:
        candidates.append({
            "type": "role", "value": semantic_role, "name": role_name,
            "stability": STABILITY["role+name"],
            "note": f'get_by_role("{semantic_role}", name="{role_name}")',
        })

    # 2. label
    for_label = data.get("forLabel","").strip()
    aria_label = data.get("ariaLabel","").strip()
    if for_label:
        candidates.append({
            "type":"label","value":for_label,
            "stability":STABILITY["label"],
            "note":f'get_by_label("{for_label}")',
        })
    elif aria_label and aria_label != role_name:
        candidates.append({
            "type":"label","value":aria_label,
            "stability":STABILITY["label"],
            "note":f'get_by_label("{aria_label}")',
        })

    # 3. text
    text = data.get("text","").strip()
    if text and len(text) <= 30 and tag in ("button","a","span","label","p"):
        if not any(c.get("name") == text for c in candidates):
            candidates.append({
                "type":"text","value":text,
                "stability":STABILITY["text"],
                "note":f'get_by_text("{text}", exact=True)',
            })

    # 4. testid
    testid = data.get("testId","").strip()
    if testid:
        candidates.append({
            "type":"testid","value":testid,
            "stability":STABILITY["testid"],
            "note":f'get_by_test_id("{testid}")',
        })

    # 5. placeholder
    ph = data.get("placeholder","").strip()
    if ph:
        candidates.append({
            "type":"placeholder","value":ph,
            "stability":STABILITY["placeholder"],
            "note":f'get_by_placeholder("{ph}")',
        })

    # 6. alt
    alt = data.get("alt","").strip()
    if alt and tag == "img":
        candidates.append({
            "type":"alt","value":alt,
            "stability":STABILITY["alt"],
            "note":f'get_by_alt_text("{alt}")',
        })

    # 7. css (stable classes only)
    css = data.get("cssSelector","").strip()
    if css and css != tag:
        candidates.append({
            "type":"css","value":css,
            "stability":STABILITY["css_stable"],
            "note":f'locator("{css}")',
        })

    candidates.sort(key=lambda c: c["stability"])
    return candidates

def print_analysis(data: dict, candidates: list[dict]) -> None:
    print(f"\n  {B}{'─'*56}{X}")
    print(f"  {B}<{data['tag']}>{X}  클래스: {D}{data.get('allClasses','(없음)')[:60]}{X}")
    if data.get("inIframe"):
        print(f"  {D}(iframe 내부 요소){X}")
    if not candidates:
        print(f"  {R}안정적인 셀렉터를 찾지 못했습니다.{X}")
        return
    for i, c in enumerate(candidates):
        star  = f"{G}★{X}" if i == 0 else f"{D}☆{X}"
        color = G if i == 0 else (Y if i == 1 else D)
        label = c["note"].split("(")[0]
        print(f"  {star} {color}{c['note']}{X}")

def candidate_to_locator(c: dict) -> dict:
    t = c["type"]
    if t == "role":
        e: dict = {"type":"role","value":c["value"]}
        if c.get("name"):
            e["name"] = c["name"]
        return e
    return {"type":t,"value":c["value"]}

# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------
def load_yaml(path: Path) -> dict:
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {k:v for k,v in raw.items() if not k.startswith("_")}
    return {}

def save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n  {G}→ 저장: {path}{X}")

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def _login(page: Page) -> None:
    print(f"  {Y}→ 로그인 페이지 열기...{X}")
    page.goto("https://nid.naver.com/nidlogin.login")
    page.wait_for_load_state("domcontentloaded", timeout=15_000)
    try:
        page.get_by_label("아이디 또는 전화번호").fill(NAVER_ID, timeout=3_000)
        page.get_by_label("비밀번호").fill(NAVER_PW, timeout=3_000)
        page.get_by_role("button", name="로그인").click(timeout=3_000)
    except Exception:
        pass
    print(f"  {C}로그인 및 기기 확인을 완료한 후 터미널에서 엔터를 누르세요.{X}")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        raise RuntimeError("로그인 취소됨.")
    print(f"  {G}→ 로그인 완료{X}")

# ---------------------------------------------------------------------------
# Main capture loop
# ---------------------------------------------------------------------------
def run_capture(page: Page, output: Path, merge: bool, css_first: bool = False) -> None:
    captured: dict = load_yaml(output) if merge else {}

    # Re-inject whenever a new frame loads
    def on_frame(frame):
        time.sleep(0.2)
        try:
            frame.evaluate(_LISTENER_JS)
        except Exception:
            pass

    page.on("frameattached",  on_frame)
    page.on("framenavigated", lambda f: on_frame(f) if f != page.main_frame else None)

    _inject_all(page)

    print(f"\n  {B}캡처 모드 시작{X}")
    print(f"  {C}클릭{X}          → 캡처 (실제 동작 차단)")
    print(f"  {C}Ctrl+클릭{X}     → 실제 동작 전달 (캡처 안 함, 모달/메뉴 열기용)")
    print(f"  {D}이름 입력 후 엔터 = 저장  |  엔터만 = 건너뜀  |  q = 종료{X}\n")

    while True:
        # Poll JS queue — page.evaluate() processes CDP events (no deadlock)
        data = None
        while data is None:
            items = _poll(page)
            if items:
                data = items[0]
                break
            time.sleep(0.15)
            try:
                page.title()  # keep connection alive
            except Exception:
                print(f"\n  {Y}브라우저가 닫혔습니다.{X}")
                save_yaml(output, captured)
                return

        candidates = analyze(data)
        print_analysis(data, candidates)

        if not candidates:
            print(f"  {D}(건너뜀 — 안정적인 셀렉터 없음){X}")
            continue

        try:
            key = input(
                f"\n  {B}키 이름{X} "
                f"(예: publish_trigger, 엔터=건너뜀, q=종료): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if key.lower() == "q":
            break
        if not key:
            print(f"  {D}건너뜀{X}")
            continue

        best = candidates[0]
        description = input(
            f"  {B}설명{X} (엔터={best['note']!r:.50s}): "
        ).strip() or best["note"]

        stable   = [c for c in candidates if c["stability"] <= STABILITY["testid"]]
        css_fb   = [c for c in candidates if c["type"] == "css"]
        to_save  = (stable + css_fb) if stable else candidates
        if css_first:
            to_save = [c for c in to_save if c["type"] == "css"] + \
                      [c for c in to_save if c["type"] != "css"]

        captured[key] = {
            "description": description,
            "locators":    [candidate_to_locator(c) for c in to_save],
        }
        print(f"  {G}✅ '{key}' 저장됨{X}")
        for e in captured[key]["locators"]:
            print(f"     {D}{e}{X}")

        save_yaml(output, captured)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="브라우저에서 요소를 클릭해 안정적인 셀렉터를 캡처합니다."
    )
    parser.add_argument("--mode",   choices=["editor", "login"], default="editor",
                        help="editor=글쓰기 페이지 캡처, login=로그인 창 캡처")
    parser.add_argument("--url",    default=None,
                        help="기본값은 모드에 따라 자동 결정")
    parser.add_argument("--output", default=None,
                        help="기본값은 모드에 따라 자동 결정")
    parser.add_argument("--merge",  action="store_true",
                        help="기존 YAML에 추가 (기존 키 유지)")
    parser.add_argument("--css-first", action="store_true",
                        help="저장 시 css 셀렉터를 최우선 순위로 배치")
    args = parser.parse_args()

    is_login_mode = args.mode == "login"

    if is_login_mode:
        url    = args.url    or LOGIN_URL
        output = Path(args.output or "selectors/naver/login.yaml")
        if not NAVER_ID:
            print(f"{R}오류: .env에 NAVER_ID가 필요합니다.{X}")
            sys.exit(1)
    else:
        url    = args.url    or WRITE_URL
        output = Path(args.output or "selectors/naver/editor.yaml")
        if not NAVER_ID or not BLOG_ID:
            print(f"{R}오류: .env에 NAVER_ID, NAVER_PW, NAVER_BLOG_ID가 필요합니다.{X}")
            sys.exit(1)

    print(f"\n{B}Naver 셀렉터 캡처 도구{X}")
    print(f"  모드 : {args.mode}")
    print(f"  URL  : {url}")
    print(f"  출력 : {output}")
    print(f"  쓰기 : {'merge' if args.merge else '새로 작성'}")

    with sync_playwright() as pw:
        browser  = pw.chromium.launch(headless=False)
        ctx_kw: dict = {"locale":"ko-KR","timezone_id":"Asia/Seoul"}
        # 로그인 모드: 세션을 일부러 무시해 로그인 창을 노출
        if not is_login_mode and Path(SESSION).exists():
            ctx_kw["storage_state"] = SESSION
            print(f"  세션 : {SESSION}")
        else:
            print(f"  세션 : 사용 안 함")
        ctx  = browser.new_context(**ctx_kw)
        page = ctx.new_page()

        print(f"\n  {Y}→ 페이지 로딩: {url}{X}")
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")

        # editor 모드에서만 자동 로그인 처리
        if not is_login_mode:
            if not Path(SESSION).exists():
                _login(page)
                page.goto(url)
                page.wait_for_load_state("domcontentloaded")
            elif "nid.naver.com" in page.url or "login" in page.url.lower():
                _login(page)
                page.goto(url)
                page.wait_for_load_state("domcontentloaded")

        time.sleep(1.5)
        run_capture(page, output, args.merge, css_first=args.css_first)
        browser.close()

    print(f"\n{G}{B}완료{X}")

if __name__ == "__main__":
    main()
