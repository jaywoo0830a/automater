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
def test_pipeline_all_options(
    editor: SmartEditorOne,
    account: AccountOption,
):
    """
    빌더의 모든 옵션을 지정한 통합 파이프라인 테스트.

    with_title   — template 기반 제목 생성
    with_content — AssetLoader 자동 감지 (이미지 없으면 텍스트 전용으로 fallback)
    with_seo     — 키워드·글자수·톤 지정
    with_image   — 아래 항목 전체:
                   · pixel_jitter / size_jitter      공통 해시 변경
                   · Exif description + GPS          공통 메타데이터 SEO
                   · preview_saturation_jitter        미세 채도 변형 (체감 안 됨)
                   · thumbnail_saturation_shift       극적 채도 변형 (컬러 톤 변경)
                   · thumbnail_text (list)            제목 줄별 오버레이
                   · thumbnail_line/letter_spacing    행간·자간 픽셀 지정
                   · filename_keyword                 파일명 키워드
    with_meta    — 예약 발행 (fixed, +2시간)
    with_setting — 기본 런타임 설정

    dry_run=True (editor fixture 기본값) — 팝오버 열림 후 발행 버튼 미클릭.
    """
    from datetime import datetime, timedelta
    from automator.options import KST, SEOOption, ImageOption

    now    = datetime.now(tz=KST)
    target = (
        now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        + timedelta(hours=2)
    )

    loader = AssetLoader()
    content_opt = loader.to_content_option(layout=[
        "Image 1",
        "Paragraph 1",
        "Image 2",
        "Paragraph 2",
        "Thumbnail 1",
        "Paragraph 3",
    ])

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(content_opt)
        .with_seo(SEOOption(
            keyword             = "강남 수학 과외",
            keyword_count_first = 3,
            keyword_count_last  = 2,
            first_para_min      = 200,
            first_para_max      = 350,
            total_min           = 600,
            total_max           = 1000,
            tone                = "review_style",
            include_question    = True,
            include_cta         = True,
        ))
        .with_image(ImageOption(
            # 공통 — 해시 변경
            pixel_jitter              = True,
            size_jitter_px            = 2,
            # 공통 — Exif SEO
            exif_description          = "강남 수학 과외",
            exif_gps_lat              = 37.4942,
            exif_gps_lng              = 127.0617,
            filename_keyword          = "강남-수학-과외",
            # preview — 미세 채도 변형 (체감 안 됨)
            preview_saturation_jitter = 0.03,
            # thumbnail — 극적 채도 변형 (컬러 톤 변경)
            thumbnail_saturation_shift    = 0.30,
            # thumbnail — 텍스트 오버레이
            thumbnail_text                = ["강남", "수학 과외"],
            thumbnail_text_color          = "#FFFFFF",
            thumbnail_line_spacing        = 24,
            thumbnail_letter_spacing      = 3,
            # 업로드 딜레이 — dry_run 이므로 0
            upload_delay_ms           = 0,
        ))
        .with_meta(MetaOption(
            schedule_mode = "fixed",
            schedule_at   = target,
        ))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


# ===========================================================================
# Real publish — --real-run 플래그로만 실행
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_real_publish(
    page: Page,
    account: AccountOption,
    real_run: bool,
):
    """
    실제 발행 테스트 — --real-run 플래그 없으면 skip.

    실행 조건:
      - pytest --real-run
      - ENV=production  (Gemini 실제 호출)
      - GEMINI_API_KEY  (.env 설정)
      - assets/images/, assets/thumbnails/ 에 파일 존재

    발행 방식: 예약 발행 (+2시간, 10분 단위 내림)
    """
    if not real_run:
        pytest.skip("--real-run 플래그 없음 — 실제 발행 건너뜀")

    from automator.options import SEOOption, ImageOption, KST
    from datetime import datetime, timedelta

    now    = datetime.now(tz=KST)
    target = (
        now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        + timedelta(hours=2)
    )

    loader = AssetLoader()
    editor = SmartEditorOne(page, account.write_url, dry_run=False)

    job = (
        NaverBlogJob
        .for_account(account)
        .with_title(TitleOption(
            template="지역+과목+학습형태+솔트",
            learning_type="과외",
            include_suffix=True,
        ))
        .with_content(loader.to_content_option(layout=[
            "Image 1",
            "Paragraph 1",
            "Image 2",
            "Paragraph 2",
            "Thumbnail 1",
            "Paragraph 3",
        ]))
        .with_seo(SEOOption(
            keyword            = "강남 수학 과외",
            keyword_count_first= 3,
            keyword_count_last = 2,
            tone               = "review_style",
            include_question   = True,
            include_cta        = True,
        ))
        .with_image(ImageOption(
            pixel_jitter                 = True,
            size_jitter_px               = 2,
            exif_description             = "강남 수학 과외",
            exif_gps_lat                 = 37.4942,
            exif_gps_lng                 = 127.0617,
            filename_keyword             = "강남-수학-과외",
            preview_saturation_jitter    = 0.03,
            thumbnail_saturation_shift   = 0.30,
            thumbnail_text               = ["강남", "수학 과외"],
            thumbnail_text_color         = "#FFFFFF",
            thumbnail_line_spacing       = 24,
            thumbnail_letter_spacing     = 3,
            upload_delay_ms              = 1500,
        ))
        .with_meta(MetaOption(
            schedule_mode = "fixed",
            schedule_at   = target,
        ))
        .with_setting(RunSetting())
    )
    job.run(editor)


# ===========================================================================
# Diagnostic: overlay, upload, representative image 단계별 진단
# ===========================================================================