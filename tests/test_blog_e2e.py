"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for Naver Blog automation.

Requires either:
  1. session_state.json (preferred), or
  2. NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env

Run:
    pytest tests/test_blog_e2e.py -m e2e -v
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v   # publish test only
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import Page

from automator.config import browser_settings
from automator.options import AccountOption, TitleOption, ContentOption, MetaOption, RunSetting
from automator.selector_loader import SelectorLoader

# Structural constants (iframe path + editor root) — not selector-dependent
_MAIN_FRAME    = "#mainFrame"
_EDITOR_BODY   = ".se-content"

# Load selector JSON once for e2e helpers
_LOGIN_SEL  = SelectorLoader.load("selectors/naver/login.json")
_EDITOR_SEL = SelectorLoader.load("selectors/naver/editor.json")
from automator.smart_editor import SmartEditorOne
from automator.job import NaverBlogJob
from automator.asset_loader import AssetLoader

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID", "")
NAVER_PW      = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH", "session_state.json")



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# E2E: Editor loads
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page, account: AccountOption):
    page.goto(account.write_url)
    page.frame_locator(_MAIN_FRAME) \
        .locator(_EDITOR_BODY) \
        .wait_for(state="visible", timeout=15_000)

@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(editor: SmartEditorOne, page: Page):
    loader = AssetLoader()
    if not loader.images:
        pytest.skip("assets/images/ 에 이미지가 없습니다.")
    image_path = loader.images[0]
    editor.open()
    editor.upload_image(image_path)
    assert page.frame_locator(_MAIN_FRAME).first.locator(_EDITOR_SEL.css("editor_image")).first.is_visible()


# ---------------------------------------------------------------------------
# E2E: Representative image
# ---------------------------------------------------------------------------

def _upload_three(editor, page):
    loader = AssetLoader()
    if not loader.images:
        pytest.skip("assets/images/ 에 이미지가 없습니다.")
    image_path = loader.images[0]
    editor.open()
    for i in range(3):
        if i > 0: editor.move_cursor_to_end()
        editor.upload_image(image_path)
    page.frame_locator(_MAIN_FRAME).first \
        .locator(_EDITOR_SEL.css("editor_image")).nth(2) \
        .wait_for(state="visible", timeout=15_000)
    assert page.frame_locator(_MAIN_FRAME).first.locator(_EDITOR_SEL.css("editor_image_rep")).count() == 3


def _assert_selected(page, index, total):
    frame   = page.frame_locator(_MAIN_FRAME).first
    buttons = frame.locator(_EDITOR_SEL.css("editor_image_rep"))
    assert frame.locator(_EDITOR_SEL.css("editor_image_rep_selected")).count() == 1
    for i in range(total):
        classes = buttons.nth(i).get_attribute("class") or ""
        if i == index: assert "se-is-selected" in classes
        else:          assert "se-is-selected" not in classes


@pytest.mark.e2e
def test_set_first_image_as_representative(editor, page):
    _upload_three(editor, page)
    editor.set_representative_image(0)
    _assert_selected(page, 0, 3)


@pytest.mark.e2e
def test_set_second_image_as_representative(editor, page):
    _upload_three(editor, page)
    editor.set_representative_image(1)
    _assert_selected(page, 1, 3)


@pytest.mark.e2e
def test_set_third_image_as_representative(editor, page):
    _upload_three(editor, page)
    editor.set_representative_image(2)
    _assert_selected(page, 2, 3)


# ===========================================================================
# E2E Pipeline Tests
#
# 모든 파이프라인 테스트는 dry_run=True (editor fixture 기본값) 상태에서
# 실행되므로 실제 발행은 일어나지 않습니다.
#
# 시나리오 구성:
#   [이미지 필요] assets/images/ 에 이미지 파일 필요 (AssetLoader 자동 감지)
#   [이미지 불필요] 텍스트 전용 / 예약 발행 검증용
#
# Run all pipeline tests:
#   pytest tests/test_blog_e2e.py -m "e2e and slow" -v
#
# Run a single scenario:
#   pytest tests/test_blog_e2e.py::test_pipeline_default -m "e2e" -v -s
# ===========================================================================


def _run_job(job, editor) -> None:
    """
    Run a NaverBlogJob and assert success.

    job.run() returns None on success and raises on failure.
    ParagraphGenerator is always mocked with UDHR stub paragraphs in pipeline tests
    (see conftest.py) — no real Gemini API calls are made here.
    """
    job.run(editor)  # raises on failure, returns None on success


# ---------------------------------------------------------------------------
# Pipeline: 브라우저 자동화 전체 흐름 검증
#
# 각 테스트는 서로 다른 핵심 경로를 커버한다.
# 제목 옵션 변형(template, learning_type, fixed_title)은 test_title_unit.py에서 커버.
#
#   full_layout  — 이미지+썸네일+단락 업로드 전체 흐름  (이미지 필요)
#   text_only    — 이미지 없이 단락만                    (이미지 불필요)
#   minimal      — 빈 레이아웃 → 단락 1개 자동 생성     (이미지 불필요)
#   scheduled    — 예약 발행 UI 설정 흐름               (이미지 불필요)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_full_layout(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    이미지 업로드 + 썸네일 + 단락이 섞인 전체 레이아웃 흐름.
    assets/images/ + assets/thumbnails/ 에서 자동 감지.
    """
    loader = AssetLoader()
    if not loader.images:
        pytest.skip("assets/images/ 에 이미지가 없습니다.")

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(loader.to_content_option(
            paragraphs=3,
            paragraph_prompt="대치동 수학 과외를 홍보하는 학부모 대상 블로그 글.",
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_text_only(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    이미지 없이 단락만 있는 흐름.
    이미지 fixture 없이도 실행 가능.
    """
    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(ContentOption(
            layout=["Paragraph 1", "Paragraph 2", "Paragraph 3"],
            paragraph_prompt="송파구 국어 과외를 홍보하는 블로그 글.",
        ))
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_minimal(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    빈 레이아웃 — open → write_title → publish 최소 경로.
    """
    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="테스트 포스트"))
        .with_content(ContentOption())
        .with_meta(MetaOption())
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_scheduled(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    예약 발행(fixed) 전체 잡 흐름.
    시/분 select 설정 후 dry_run으로 종료.
    """
    from datetime import datetime, timedelta
    from automator.options import KST

    now    = datetime.now(tz=KST)
    target = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0) + timedelta(hours=2)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="예약 발행 테스트"))
        .with_content(ContentOption(layout=["Paragraph 1"]))
        .with_meta(MetaOption(
            schedule_mode="fixed",
            schedule_at=target,
        ))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


# ===========================================================================
# Diagnostic: overlay, upload, representative image 단계별 진단
# ===========================================================================