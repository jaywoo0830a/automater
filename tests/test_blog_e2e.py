"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.

Requires either:
  1. A valid session_state.json, OR
  2. NAVER_ID / NAVER_PW in .env

All selectors are loaded from:
  - selectors/naver/login.json
  - selectors/naver/editor.json

Run with:
    pytest tests/test_blog_e2e.py -m e2e -v
"""
import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from automator.config import settings
from automator.blog import (
    MAIN_FRAME,
    EDITOR_CONTENT,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    BlogPost,
    LOGIN_URL,
    session_exists,
    login,
    wait_for_editor,
    fill_title,
    fill_body,
    upload_image,
    set_representative_image,
    click_publish_trigger,
    click_publish_confirm,
    post_blog,
)

load_dotenv()

SESSION_PATH     = os.getenv("SESSION_PATH", "session_state.json")
NAVER_ID         = os.getenv("NAVER_ID", "")
NAVER_PW         = os.getenv("NAVER_PW", "")
LOGIN_JSON_PATH  = os.getenv("LOGIN_JSON_PATH",  "selectors/naver/login.json")
EDITOR_JSON_PATH = os.getenv("EDITOR_JSON_PATH", "selectors/naver/editor.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_instance():
    """Launch a single Chromium browser for the whole test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()


@pytest.fixture(scope="session")
def auth_context(browser_instance: Browser):
    """
    Provide an authenticated BrowserContext.
    Prefers session_state.json; falls back to env-var login.
    """
    if session_exists(SESSION_PATH):
        ctx = browser_instance.new_context(storage_state=SESSION_PATH)
    elif NAVER_ID and NAVER_PW:
        ctx  = browser_instance.new_context()
        page = ctx.new_page()
        login(page, NAVER_ID, NAVER_PW, LOGIN_JSON_PATH)
        ctx.storage_state(path=SESSION_PATH)
        page.close()
    else:
        pytest.skip("No session file or credentials. Set NAVER_ID/NAVER_PW in .env.")

    yield ctx
    ctx.close()


@pytest.fixture()
def page(auth_context: BrowserContext):
    """Open a fresh page per test, then close it."""
    p = auth_context.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# E2E: Editor loads correctly
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page):
    """Smart Editor iframe renders after navigating to the write page."""
    page.goto(settings.write_url)
    page.frame_locator(MAIN_FRAME) \
        .locator(EDITOR_CONTENT) \
        .wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
def test_two_placeholder_spans_exist(page: Page):
    """At least 2 se-placeholder spans exist (title + body)."""
    page.goto(settings.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    count = frame.locator("span.se-placeholder.__se_placeholder").count()
    assert count >= 2, f"Expected >= 2 placeholder spans, found {count}"


@pytest.mark.e2e
def test_placeholder_ids_contain_uuid_prefix(page: Page):
    """Placeholder parent IDs follow the SE-{uuid} pattern."""
    page.goto(settings.write_url)
    frame = page.frame_locator(MAIN_FRAME)
    frame.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
    parent_id = (
        frame.locator("span.se-placeholder.__se_placeholder")
             .nth(0)
             .locator("..")
             .get_attribute("id")
    )
    assert parent_id and parent_id.startswith("SE-"), (
        f"Expected id to start with 'SE-', got: {parent_id!r}"
    )


# ---------------------------------------------------------------------------
# E2E: Image upload
# ---------------------------------------------------------------------------

IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "smile.jpg")


@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(page: Page):
    """Clicking image trigger and selecting a file inserts an image."""
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    wait_for_editor(page)
    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    frame = page.frame_locator(MAIN_FRAME).first
    assert frame.locator(UPLOADED_IMAGE).first.is_visible()



# ---------------------------------------------------------------------------
# E2E: Representative (thumbnail) image
#
# 업로드 간 body 클릭을 삽입하는 이유:
#   upload_image()는 toolbar 버튼 클릭 → 파일 선택 순으로 동작한다.
#   두 번째 업로드부터 에디터 포커스가 첫 번째 이미지 블록에 머물면
#   같은 블록에 덮어씌워지는 경우가 있다.
#   body 영역을 클릭해 커서를 본문 끝으로 이동시킨 뒤 업로드하면
#   각 이미지가 독립된 블록으로 삽입된다.
#
# 향후 시나리오 예시:
#   "첫 이미지 삽입 → 단락 3개 → 두 번째 이미지 → 단락 3개 → 마지막 이미지를 썸네일"
#   → fill_body() 호출을 upload_image() 사이에 끼워 넣으면 된다.
# ---------------------------------------------------------------------------

def _move_cursor_to_end(page: Page) -> None:
    """
    이미지 업로드 후 커서를 본문 끝으로 이동시킨다.

    _editor_frame()과 동일한 자동 감지 로직으로 iframe/page 레벨을 모두 처리한다.
    """
    try:
        frame = page.frame_locator(MAIN_FRAME).first
        frame.locator(EDITOR_CONTENT).click()
    except Exception:
        page.locator(EDITOR_CONTENT).click()
    page.keyboard.press("Control+End")


def _upload_three_images(page: Page) -> None:
    """
    Upload 3 images into the editor.

    각 업로드 사이에 커서를 본문 끝으로 이동시켜
    이미지가 독립된 블록으로 삽입되도록 한다.
    """
    wait_for_editor(page)

    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    _move_cursor_to_end(page)
    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    _move_cursor_to_end(page)
    upload_image(page, IMAGE_PATH, EDITOR_JSON_PATH)

    # Wait until all 3 image blocks are attached (rep buttons are hidden until hover)
    frame        = page.frame_locator(MAIN_FRAME).first
    image_blocks = frame.locator(UPLOADED_IMAGE)
    image_blocks.nth(2).wait_for(state="visible", timeout=15_000)
    rep_buttons = frame.locator(REP_IMAGE_BUTTON)
    assert rep_buttons.count() == 3, (
        f"Expected 3 rep buttons after uploading 3 images, got {rep_buttons.count()}"
    )


def _assert_only_nth_is_selected(frame, rep_buttons, index: int, total: int) -> None:
    """
    Assert that exactly one rep button is selected, and it is the one at ``index``.
    """
    selected = frame.locator(REP_IMAGE_BUTTON_SELECTED)
    assert selected.count() == 1, (
        f"Expected exactly 1 selected rep button, got {selected.count()}"
    )
    for i in range(total):
        classes = rep_buttons.nth(i).get_attribute("class") or ""
        if i == index:
            assert "se-is-selected" in classes, (
                f"Expected image[{i}] to be selected (se-is-selected), classes: {classes!r}"
            )
        else:
            assert "se-is-selected" not in classes, (
                f"Expected image[{i}] NOT to be selected, classes: {classes!r}"
            )


@pytest.mark.e2e
def test_set_first_image_as_representative(page: Page):
    """
    3장 업로드 후 첫 번째(index=0) 이미지를 썸네일로 설정하고 검증한다.
    첫 번째 이미지는 기본값이므로 클릭 없이 이미 선택되어 있어야 한다.
    """
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    _upload_three_images(page)

    frame       = page.frame_locator(MAIN_FRAME).first
    rep_buttons = frame.locator(REP_IMAGE_BUTTON)

    # index=0 is selected by default — explicitly set it to confirm the API works
    set_representative_image(page, index=0)
    _assert_only_nth_is_selected(frame, rep_buttons, index=0, total=3)


@pytest.mark.e2e
def test_set_second_image_as_representative(page: Page):
    """3장 업로드 후 두 번째(index=1) 이미지를 썸네일로 설정하고 검증한다."""
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    _upload_three_images(page)

    frame       = page.frame_locator(MAIN_FRAME).first
    rep_buttons = frame.locator(REP_IMAGE_BUTTON)

    set_representative_image(page, index=1)
    _assert_only_nth_is_selected(frame, rep_buttons, index=1, total=3)


@pytest.mark.e2e
def test_set_third_image_as_representative(page: Page):
    """3장 업로드 후 세 번째(index=2) 이미지를 썸네일로 설정하고 검증한다."""
    if not os.path.exists(IMAGE_PATH):
        pytest.skip(f"Test image not found: {IMAGE_PATH!r}")

    page.goto(settings.write_url)
    _upload_three_images(page)

    frame       = page.frame_locator(MAIN_FRAME).first
    rep_buttons = frame.locator(REP_IMAGE_BUTTON)

    set_representative_image(page, index=2)
    _assert_only_nth_is_selected(frame, rep_buttons, index=2, total=3)


# ---------------------------------------------------------------------------
# E2E: Full publish sequence
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_full_post_sequence(page: Page):
    """
    Full sequence: navigate → fill title → fill body → publish.
    WARNING: publishes a real post. Delete it afterward.
    Run with: pytest tests/test_blog_e2e.py::test_full_post_sequence -m "e2e and slow"
    """
    page.goto(settings.write_url)
    wait_for_editor(page)
    fill_title(page, "[자동화 테스트] Playwright로 작성한 포스트", EDITOR_JSON_PATH)
    fill_body(
        page,
        "안녕하세요! 이 글은 Playwright 자동화 테스트로 작성된 포스트입니다.\n\n"
        "테스트 완료 후 삭제 예정입니다.",
        EDITOR_JSON_PATH,
    )
    click_publish_trigger(page, EDITOR_JSON_PATH)
    click_publish_confirm(page, EDITOR_JSON_PATH)


@pytest.mark.e2e
@pytest.mark.slow
def test_title_and_body_visible_before_publish(page: Page):
    """Fills title and body, verifies publish trigger is visible — does NOT publish."""
    page.goto(settings.write_url)
    wait_for_editor(page)
    fill_title(page, "[자동화 테스트] 발행 안 함", EDITOR_JSON_PATH)
    fill_body(page, "발행하지 않는 테스트입니다.", EDITOR_JSON_PATH)
    click_publish_trigger(page, EDITOR_JSON_PATH)
