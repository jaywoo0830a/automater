"""
tests/test_debug.py
-------------------
임시 진단 테스트 모음.

문제 해결 후 이 파일의 테스트들은 삭제한다.
실행: pytest tests/test_debug.py -m e2e -v -s
"""
import json
import os

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from automator.blog import (
    EDITOR_CONTENT,
    IMAGE_COMPONENT,
    MAIN_FRAME,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    UPLOADED_IMAGE,
    fill_body,
    fill_title,
    login,
    session_exists,
    set_representative_image,
    upload_image,
    wait_for_editor,
)
from automator.config import settings

load_dotenv()

SESSION_PATH     = os.getenv("SESSION_PATH", "session_state.json")
EDITOR_JSON_PATH = os.getenv("EDITOR_JSON_PATH", "selectors/naver/editor.json")
LOGIN_JSON_PATH  = os.getenv("LOGIN_JSON_PATH",  "selectors/naver/login.json")
IMAGE_PATH       = os.getenv("TEST_IMAGE_PATH", "smile.jpg")
NAVER_ID         = os.getenv("NAVER_ID", "")
NAVER_PW         = os.getenv("NAVER_PW", "")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def auth_context(browser_instance: Browser):
    if session_exists(SESSION_PATH):
        ctx = browser_instance.new_context(storage_state=SESSION_PATH)
    elif NAVER_ID and NAVER_PW:
        ctx = browser_instance.new_context()
        pg  = ctx.new_page()
        login(pg, NAVER_ID, NAVER_PW, LOGIN_JSON_PATH)
        ctx.storage_state(path=SESSION_PATH)
        pg.close()
    else:
        pytest.skip("No session or credentials available")
    yield ctx
    ctx.close()


@pytest.fixture
def page(auth_context: BrowserContext):
    pg = auth_context.new_page()
    pg.goto(settings.write_url)
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# 진단 1: page 레벨 + iframe 레벨 양쪽에서 도움말 패널 탐색
# ---------------------------------------------------------------------------

_HELP_JS = """() => {
    const panel = document.querySelector('.se-help-title');
    if (!panel) return JSON.stringify({found: false});

    // 조상 체인 (최대 8단계)
    const chain = [];
    let el = panel.parentElement;
    while (el && chain.length < 8) {
        chain.push({ tag: el.tagName.toLowerCase(), id: el.id || null, cls: el.className || null });
        el = el.parentElement;
    }

    // 닫기 버튼 후보: class/aria/text 중 하나라도 '닫'/'close'/'Close' 포함
    const buttons = [...document.querySelectorAll('button, [role=button]')].map(b => ({
        cls:       b.className,
        text:      b.textContent.trim().slice(0, 40),
        ariaLabel: b.getAttribute('aria-label'),
        visible:   b.offsetParent !== null,
    })).filter(b =>
        /close|Close|닫/i.test(b.cls + b.ariaLabel + b.text)
    );

    return JSON.stringify({found: true, chain, buttons}, null, 2);
}"""


@pytest.mark.e2e
def test_debug_help_panel_structure(page: Page):
    """
    발행 버튼을 가로막는 도움말 패널(.se-help-title)의 구조를 출력한다.
    에러 메시지에서 container__HW_tc 가 page 레벨에 있었으므로
    page.evaluate()와 iframe.evaluate() 양쪽을 탐색한다.
    """
    wait_for_editor(page)

    # 1) page 레벨
    page_data = json.loads(page.evaluate(_HELP_JS))
    print("\n=== [page 레벨] 도움말 패널 ===")
    if page_data["found"]:
        print("  조상 체인:")
        for c in page_data["chain"]:
            print(f"    {c['tag']}  id={c['id']!r}  cls={c['cls']!r}")
        print("  닫기 버튼 후보:")
        for b in page_data["buttons"]:
            print(f"    cls={b['cls']!r}  aria={b['ariaLabel']!r}  text={b['text']!r}  visible={b['visible']}")
    else:
        print("  패널 없음")

    # 2) editor iframe 레벨
    editor_frame = next((f for f in page.frames if f != page.main_frame), None)
    iframe_data  = {"found": False}
    if editor_frame:
        iframe_data = json.loads(editor_frame.evaluate(_HELP_JS))
        print("\n=== [iframe 레벨] 도움말 패널 ===")
        if iframe_data["found"]:
            print("  조상 체인:")
            for c in iframe_data["chain"]:
                print(f"    {c['tag']}  id={c['id']!r}  cls={c['cls']!r}")
            print("  닫기 버튼 후보:")
            for b in iframe_data["buttons"]:
                print(f"    cls={b['cls']!r}  aria={b['ariaLabel']!r}  text={b['text']!r}")
        else:
            print("  패널 없음")

    if not page_data["found"] and not iframe_data["found"]:
        pytest.skip("도움말 패널을 찾지 못함 — 에디터 첫 로드 시에만 나타날 수 있음")

    assert page_data["found"] or iframe_data["found"]


# ---------------------------------------------------------------------------
# 진단 2: container__HW_* 전수 조사
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_help_container_buttons(page: Page):
    """
    에러에 등장한 container__HW_tc 컨테이너 내부의 모든 버튼을 전수 출력한다.
    닫기 버튼의 정확한 셀렉터를 파악하기 위한 테스트.
    """
    wait_for_editor(page)

    result = json.loads(page.evaluate("""() => {
        const containers = document.querySelectorAll('[class*="container__HW"]');
        return JSON.stringify([...containers].map(c => ({
            cls: c.className,
            buttons: [...c.querySelectorAll('button, [role=button], a')].map(b => ({
                tag:       b.tagName.toLowerCase(),
                cls:       b.className,
                text:      b.textContent.trim().slice(0, 40),
                ariaLabel: b.getAttribute('aria-label'),
                visible:   b.offsetParent !== null,
            })),
        })), null, 2);
    }"""))

    print("\n=== container__HW_* 내부 버튼 전수 조사 ===")
    for c in result:
        print(f"\n  컨테이너 cls: {c['cls']!r}")
        for b in c["buttons"]:
            print(f"    {b['tag']}  cls={b['cls']!r}  aria={b['ariaLabel']!r}"
                  f"  text={b['text']!r}  visible={b['visible']}")

    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 진단 3: rep 버튼 JS 클릭
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_rep_button_js_click(page: Page):
    """
    JavaScript dispatchEvent로 rep 버튼을 직접 클릭한다.
    Playwright의 visibility 체크를 우회하여 hidden 버튼도 강제 클릭 가능한지 확인.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    wait_for_editor(page)
    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    editor_frame = next((f for f in page.frames if f != page.main_frame), page.main_frame)

    btn_count  = editor_frame.locator(REP_IMAGE_BUTTON).count()
    is_visible = editor_frame.locator(REP_IMAGE_BUTTON).first.is_visible()
    print(f"\n  rep button count : {btn_count}")
    print(f"  first btn visible: {is_visible}")

    result = editor_frame.evaluate("""(selector) => {
        const btns = document.querySelectorAll(selector);
        if (!btns.length) return 'no buttons found';
        const btn = btns[0];
        btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        return `after=${btn.classList.contains('se-is-selected')} class=${btn.className}`;
    }""", REP_IMAGE_BUTTON)

    print(f"  JS click result  : {result}")

    selected_count = editor_frame.locator(REP_IMAGE_BUTTON_SELECTED).count()
    print(f"  selected count   : {selected_count}")
    assert selected_count >= 1


# ---------------------------------------------------------------------------
# 진단: 발행 버튼 위치 — page 레벨 vs iframe 레벨
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_debug_publish_trigger_location(page: Page):
    """
    발행 버튼이 page 레벨(툴바)에 있는지, iframe 안에 있는지 파악한다.
    도움말 패널이 클릭을 가로막는 경우의 구조도 함께 출력한다.
    """
    import json as _json

    wait_for_editor(page)

    editor_frame = next((f for f in page.frames if f != page.main_frame), page.main_frame)

    # 1. page 레벨에서 '발행' 텍스트 요소 검색
    page_result = page.evaluate("""() => {
        const els = [...document.querySelectorAll('*')].filter(
            el => el.textContent.trim() === '발행' && el.children.length === 0
        );
        return els.map(el => ({
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            inIframe: false,
            rect: el.getBoundingClientRect(),
            pointerEvents: getComputedStyle(el).pointerEvents,
            visibility: getComputedStyle(el).visibility,
        }));
    }""")

    # 2. iframe 안에서 검색
    iframe_result = editor_frame.evaluate("""() => {
        const els = [...document.querySelectorAll('*')].filter(
            el => el.textContent.trim() === '발행' && el.children.length === 0
        );
        return els.map(el => ({
            tag: el.tagName,
            cls: el.className,
            id: el.id,
            inIframe: true,
            rect: el.getBoundingClientRect(),
            pointerEvents: getComputedStyle(el).pointerEvents,
            visibility: getComputedStyle(el).visibility,
        }));
    }""")

    # 3. 도움말 패널 확인
    help_in_iframe = editor_frame.evaluate("""() => {
        const h = document.querySelector('.se-help-title');
        if (!h) return null;
        const container = h.closest('[class*="container"]') || h.parentElement;
        return {
            title: h.textContent,
            containerCls: container?.className,
            buttons: [...container?.querySelectorAll('button') || []].map(b => ({
                cls: b.className,
                ariaLabel: b.getAttribute('aria-label'),
                text: b.textContent.trim().slice(0, 20),
            })),
        };
    }""")

    print("\n=== page 레벨 발행 요소 ===")
    for el in page_result:
        print(f"  <{el['tag']}> cls={el['cls']!r}  ptrEvents={el['pointerEvents']}  vis={el['visibility']}")

    print("\n=== iframe 레벨 발행 요소 ===")
    for el in iframe_result:
        print(f"  <{el['tag']}> cls={el['cls']!r}  ptrEvents={el['pointerEvents']}  vis={el['visibility']}")

    print("\n=== 도움말 패널 (iframe 안) ===")
    if help_in_iframe:
        print(f"  containerCls: {help_in_iframe['containerCls']!r}")
        for b in help_in_iframe['buttons']:
            print(f"  btn  cls={b['cls']!r}  aria={b['ariaLabel']!r}  text={b['text']!r}")
    else:
        print("  없음")

    # page 레벨 또는 iframe 레벨 중 하나에는 있어야 함
    total = len(page_result) + len(iframe_result)
    assert total > 0, "발행 버튼 요소를 어디서도 찾지 못함"
