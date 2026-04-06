"""
tests/e2e/test_debug_rep_media.py
-----------------------------------
대표이미지 설정 후 ParagraphStep이 멈추는 문제 디버그 테스트.

실행:
    pytest tests/e2e/test_debug_rep_media.py -v -s --timeout=300

서버(VNC) 환경에서만 재현되는 문제를 진단하기 위해
각 단계에서 DOM 상태를 상세 로그로 출력한다.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from automator.smart_editor import SmartEditorOne, _MAIN_FRAME, _EDITOR_BODY
from automator.browser_actions import find_editor_frame, find_js_frame
from automator.options import AccountOption

from playwright.sync_api import Page

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset(subdir: str, index: int) -> str | None:
    base = Path("assets") / subdir
    files = sorted(base.iterdir()) if base.is_dir() else []
    return str(files[index]) if index < len(files) else None


def _dump_state(page: Page, editor: SmartEditorOne, label: str):
    """에디터 DOM 상태를 상세 로그로 출력."""
    log.info("━━━ %s ━━━", label)

    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    sel = editor._sel()

    # paragraph containers
    paras = sel.locator(frame, "editor_paragraph_container")
    para_count = paras.count()
    log.info("  paragraph_container: %d개", para_count)
    if para_count > 0:
        last = paras.last
        try:
            log.info("  last paragraph — visible: %s, box: %s",
                     last.is_visible(), last.bounding_box())
        except Exception as e:
            log.error("  last paragraph 접근 실패: %s", e)

    # image blocks
    imgs = sel.locator(frame, "editor_image_block")
    log.info("  image_block: %d개", imgs.count())

    # 이미지 선택/오버레이 상태
    for css_class in ("se-selection", "se-is-selected",
                      "se-floating-material-container",
                      "se-component-selected"):
        count = frame.locator(f".{css_class}").count()
        if count > 0:
            log.info("  .%s 발견: %d개", css_class, count)

    # top-level activeElement
    try:
        active = page.evaluate(
            "() => { const e = document.activeElement; "
            "return e ? e.tagName + (e.id ? '#'+e.id : '') : 'null'; }"
        )
        log.info("  top activeElement: %s", active)
    except Exception:
        pass

    # iframe activeElement
    try:
        js = find_js_frame(page, url_fragment="mainFrame")
        if js:
            inner = js.evaluate(
                "() => { const e = document.activeElement; "
                "return e ? e.tagName + '.' + (e.className||'').substring(0,60) : 'null'; }"
            )
            log.info("  iframe activeElement: %s", inner)
    except Exception as e:
        log.info("  iframe activeElement 실패: %s", e)

    # contenteditable 상태
    try:
        js = find_js_frame(page, url_fragment="mainFrame")
        if js:
            editable = js.evaluate(
                """() => {
                    const body = document.querySelector('.se-content');
                    if (!body) return 'body not found';
                    return `contenteditable=${body.contentEditable}, `
                         + `pointerEvents=${getComputedStyle(body).pointerEvents}`;
                }"""
            )
            log.info("  .se-content: %s", editable)
    except Exception:
        pass

    log.info("━━━ /%s ━━━", label)


def _try_type(page: Page, editor: SmartEditorOne, strategy_name: str, action, text: str) -> bool:
    """전략 실행 후 타이핑 시도, 성공 여부 반환."""
    log.info("전략: %s", strategy_name)
    action()
    time.sleep(0.5)

    page.keyboard.type(text)
    time.sleep(0.5)

    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    sel = editor._sel()
    last = sel.locator(frame, "editor_paragraph_container").last
    actual = last.inner_text() if last.count() > 0 else ""
    found = text in actual

    if found:
        log.info("  → ✓ 성공: %r", actual[:80])
    else:
        log.error("  → ✗ 실패: last paragraph=%r", actual[:80])
        _dump_state(page, editor, f"{strategy_name} 실패 후")

    return found


# ---------------------------------------------------------------------------
# Test 1: 단계별 커서 상태 점검
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_rep_media_cursor_state(
    page: Page, editor: SmartEditorOne, account: AccountOption,
):
    """대표이미지 설정 후 커서 상태를 단계별로 점검."""
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)
    if not image or not thumb:
        pytest.skip("assets/images/ 와 assets/thumbnails/ 필요")

    editor.open()
    editor.write_title("디버그: rep_media 커서 상태")
    _dump_state(page, editor, "제목 입력 후")

    # 이미지 5장 업로드 (실제 캠페인과 동일)
    for i in range(5):
        src = thumb if i == 4 else image
        editor.upload_file(src)
        editor.move_cursor("end")
        time.sleep(1)
    _dump_state(page, editor, "이미지 5장 업로드 후")

    # 대표이미지 설정
    log.info("set_representative_media(4) 호출")
    editor.set_representative_media(4)
    _dump_state(page, editor, "set_representative_media 직후")

    # move_cursor (runner가 하는 것과 동일)
    editor.move_cursor("end")
    time.sleep(0.3)
    _dump_state(page, editor, "move_cursor(end) 후")

    # insert_text 시도
    test_text = "REP_MEDIA_TEST_TEXT_12345"
    log.info("insert_text 시도: %r", test_text)
    editor.insert_text(test_text, 2)
    time.sleep(1)

    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    body_text = frame.locator(_EDITOR_BODY).inner_text()
    found = test_text in body_text
    log.info("insert_text 결과: %s", "✓ 성공" if found else "✗ 실패")

    if not found:
        _dump_state(page, editor, "insert_text 실패 후")

    assert found, f"대표이미지 후 텍스트 입력 실패. body에서 {test_text!r} 못 찾음"


# ---------------------------------------------------------------------------
# Test 2: 복구 전략 비교
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_rep_media_recovery_strategies(
    page: Page, editor: SmartEditorOne, account: AccountOption,
):
    """대표이미지 후 여러 복구 전략을 순서대로 시도."""
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)
    if not image or not thumb:
        pytest.skip("assets/images/ 와 assets/thumbnails/ 필요")

    editor.open()
    editor.write_title("디버그: 복구 전략 비교")

    for i in range(5):
        src = thumb if i == 4 else image
        editor.upload_file(src)
        editor.move_cursor("end")
        time.sleep(1)

    # 대표이미지 — 원래 코드의 커서 복구를 우회하기 위해 직접 호출
    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    sel = editor._sel()

    block = sel.locator(frame, "editor_image_block").nth(4)
    block.wait_for(state="visible", timeout=5_000)
    block.hover()

    from automator.browser_actions import locator_dispatch_click, wait_until_attached
    result = locator_dispatch_click(
        sel.locator(frame, "editor_image_rep"),
        index=4,
    )
    log.info("대표이미지 JS 결과: %s", result)

    wait_until_attached(
        sel.locator(frame, "editor_image_rep_selected").first,
        timeout_ms=5_000,
    )
    _dump_state(page, editor, "대표이미지 직후 (커서 복구 전)")

    # 전략들
    strategies = [
        ("1. _click_last_paragraph(force=True)",
         lambda: editor._click_last_paragraph(frame)),

        ("2. Escape → Ctrl+End",
         lambda: (page.keyboard.press("Escape"),
                  time.sleep(0.3),
                  page.keyboard.press("Control+End"))),

        ("3. Escape → Ctrl+End → _click_editor_bottom",
         lambda: (page.keyboard.press("Escape"),
                  time.sleep(0.3),
                  page.keyboard.press("Control+End"),
                  time.sleep(0.3),
                  editor._click_editor_bottom(frame))),

        ("4. Escape → _click_editor_bottom → _click_last_paragraph",
         lambda: (page.keyboard.press("Escape"),
                  time.sleep(0.3),
                  editor._click_editor_bottom(frame),
                  time.sleep(0.3),
                  editor._click_last_paragraph(frame))),

        ("5. Escape → 에디터 body 직접 클릭 → Ctrl+End",
         lambda: (page.keyboard.press("Escape"),
                  time.sleep(0.3),
                  frame.locator(_EDITOR_BODY).click(
                      position={"x": 400, "y": 100}, force=True),
                  time.sleep(0.3),
                  page.keyboard.press("Control+End"))),

        ("6. Escape → iframe focus → Ctrl+End → Enter",
         lambda: (page.keyboard.press("Escape"),
                  time.sleep(0.3),
                  page.frame_locator(_MAIN_FRAME).locator(_EDITOR_BODY).click(force=True),
                  time.sleep(0.3),
                  page.keyboard.press("Control+End"),
                  time.sleep(0.3),
                  page.keyboard.press("Enter"))),

        ("7. JS DOM 강제 조작 (_force_clear_image_selection)",
         lambda: editor._force_clear_image_selection()),
    ]

    for name, action in strategies:
        marker = f"[{name[:5]}]OK"
        if _try_type(page, editor, name, action, marker):
            log.info("━━━ 성공 전략: %s ━━━", name)
            return

    _dump_state(page, editor, "모든 전략 실패 후")
    pytest.fail("모든 복구 전략 실패")


# ---------------------------------------------------------------------------
# Test: se-canvas-bottom (본문 추가) 클릭 전략
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_canvas_bottom_click_after_rep_media(
    page: Page, editor: SmartEditorOne, account: AccountOption,
):
    """
    대표이미지 설정 후 div.se-canvas-bottom (본문 추가) 클릭으로 탈출 시도.

    이 영역은 에디터 캔버스 하단의 "본문 추가" 영역으로,
    클릭하면 새 paragraph를 만들고 커서를 그곳으로 이동시킨다.
    """
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)
    if not image or not thumb:
        pytest.skip("assets/images/ 와 assets/thumbnails/ 필요")

    editor.open()
    editor.write_title("디버그: canvas-bottom 클릭")

    for i in range(5):
        src = thumb if i == 4 else image
        editor.upload_file(src)
        editor.move_cursor("end")
        time.sleep(1)

    # 대표이미지 — _force_clear_image_selection 우회를 위해 직접 호출
    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    sel = editor._sel()

    block = sel.locator(frame, "editor_image_block").nth(4)
    block.wait_for(state="visible", timeout=5_000)
    block.hover()

    from automator.browser_actions import locator_dispatch_click, wait_until_attached
    locator_dispatch_click(
        sel.locator(frame, "editor_image_rep"),
        index=4,
    )
    wait_until_attached(
        sel.locator(frame, "editor_image_rep_selected").first,
        timeout_ms=5_000,
    )

    _dump_state(page, editor, "대표이미지 직후")

    # ── div.se-canvas-bottom 클릭 ──
    log.info("div.se-canvas-bottom 클릭 시도")
    canvas_bottom = frame.locator("div.se-canvas-bottom")
    count = canvas_bottom.count()
    log.info("  se-canvas-bottom 개수: %d", count)

    if count == 0:
        # role 기반으로 fallback
        canvas_bottom = frame.get_by_role("div", name="본문 추가")
        log.info("  role 기반 fallback 사용")

    canvas_bottom.first.click()
    time.sleep(0.5)
    _dump_state(page, editor, "se-canvas-bottom 클릭 후")

    # ── 타이핑 시도 ──
    test_text = "CANVAS_BOTTOM_TEST_99999"
    log.info("keyboard.type 호출: %r", test_text)
    page.keyboard.type(test_text)
    time.sleep(1)

    body_text = frame.locator(_EDITOR_BODY).inner_text()
    found = test_text in body_text

    log.info("결과: %s", "✓ 성공" if found else "✗ 실패")
    if not found:
        _dump_state(page, editor, "타이핑 실패 후")

    assert found, (
        f"se-canvas-bottom 클릭 후 타이핑 실패. "
        f"body에서 {test_text!r} 못 찾음."
    )


# ---------------------------------------------------------------------------
# Test 3: JS 강제 복구 단독 검증
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_js_force_clear_after_rep_media(
    page: Page, editor: SmartEditorOne, account: AccountOption,
):
    """
    set_representative_media → _force_clear_image_selection (자동 호출됨) →
    insert_text 가 정상 동작하는지 검증.

    production 코드의 set_representative_media 안에 이미 _force_clear_image_selection
    이 포함되어 있으므로, 추가 복구 없이 바로 텍스트 입력이 되어야 한다.
    """
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)
    if not image or not thumb:
        pytest.skip("assets/images/ 와 assets/thumbnails/ 필요")

    editor.open()
    editor.write_title("디버그: JS 강제 복구")

    for i in range(5):
        src = thumb if i == 4 else image
        editor.upload_file(src)
        editor.move_cursor("end")
        time.sleep(1)
    _dump_state(page, editor, "이미지 5장 업로드 후")

    # 대표이미지 — 내부에서 _force_clear_image_selection 자동 호출
    log.info("set_representative_media(4) 호출 — JS 복구 자동 실행")
    editor.set_representative_media(4)
    _dump_state(page, editor, "set_representative_media + JS 복구 후")

    # JS 복구가 selection을 마지막 paragraph 끝에 두었으므로
    # _click_last_paragraph 없이도 바로 keyboard.type이 동작해야 함
    test_text = "JS_FORCE_CLEAR_TEST_67890"
    log.info("keyboard.type 직접 호출 (insert_text 우회)")
    page.keyboard.type(test_text)
    time.sleep(1)

    frame = find_editor_frame(page, _MAIN_FRAME, _EDITOR_BODY)
    body_text = frame.locator(_EDITOR_BODY).inner_text()
    found = test_text in body_text

    log.info("결과: %s", "✓ 성공 — JS 복구만으로 타이핑 가능" if found else "✗ 실패")

    if not found:
        _dump_state(page, editor, "타이핑 실패 후")

    assert found, (
        f"JS 강제 복구 후 keyboard.type 실패. "
        f"body에서 {test_text!r} 못 찾음. "
        f"커서가 여전히 이미지 블록에 갇혀있을 가능성."
    )


# ---------------------------------------------------------------------------
# Test 4: 실제 캠페인 블록 순서로 runner.run() 재현
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_campaign_layout_with_runner(
    page: Page, editor: SmartEditorOne, account: AccountOption,
):
    """실제 캠페인 레이아웃으로 runner.run() 재현."""
    from automator.options import (
        Section, ImageBlock, FeaturedImageBlock,
        ParagraphBlock, DividerBlock, TextBlock,
    )
    from automator.contracts import PostingSpec
    from automator.stubs import StubTextGenerator, NoopImageProcessor
    from automator.spec_validator import SpecValidator
    from automator.content_builder import ContentBuilder
    from automator.runner import JobRunner

    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)
    if not image or not thumb:
        pytest.skip("assets/images/ 와 assets/thumbnails/ 필요")

    blocks = [
        ImageBlock(path=image, wait_ms=5000),
        DividerBlock(),
        ImageBlock(path=image, wait_ms=5000),
        ImageBlock(path=image, wait_ms=5000),
        DividerBlock(),
        ImageBlock(path=image, wait_ms=5000),
        TextBlock(content="텍스트 블록 — 대표이미지 직전"),
        FeaturedImageBlock(path=thumb, wait_ms=5000),
        ParagraphBlock(prompt="대표이미지 이후 AI 텍스트 블록"),
    ]

    spec = PostingSpec(
        account=account,
        title="디버그: 캠페인 레이아웃 runner.run()",
        body=(Section(blocks=tuple(blocks)),),
    )

    runner = JobRunner(SpecValidator(), ContentBuilder(StubTextGenerator(), NoopImageProcessor()))
    log.info("runner.run() 시작 — %d개 블록", len(blocks))
    runner.run(spec, editor)
    log.info("runner.run() 완료")
