"""
tests/test_blog_e2e.py
----------------------
End-to-end tests for blog automation.

Requires:
  session_state.json  또는  NAVER_ID / NAVER_PW / NAVER_BLOG_ID in .env

Run:
    pytest tests/test_blog_e2e.py -m e2e -v
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v
"""

import os
import pytest

from dotenv import load_dotenv
from playwright.sync_api import Page

from automator.config import browser_settings
from automator.options import (
    AccountOption, TitleOption, RunSetting,
    TextBlock, ImageBlock, FeaturedBlock,
    PublishOption, SEOOption, MediaOption,
)
from automator.selector_loader import SelectorLoader
from automator.smart_editor import SmartEditorOne
from automator.job import PostingJob
from automator.editor import ImageStep
from automator.asset_loader import AssetLoader

_MAIN_FRAME  = "#mainFrame"
_EDITOR_BODY = ".se-content"

_LOGIN_SEL  = SelectorLoader.load("selectors/naver/login.json")
_EDITOR_SEL = SelectorLoader.load("selectors/naver/editor.json")

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID", "")
NAVER_PW      = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH", "session_state.json")


# ---------------------------------------------------------------------------
# E2E: Editor loads
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_editor_iframe_is_visible(page: Page, account: AccountOption):
    page.goto(f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&")
    page.frame_locator(_MAIN_FRAME) \
        .locator(_EDITOR_BODY) \
        .wait_for(state="visible", timeout=15_000)


@pytest.mark.e2e
def test_image_upload_inserts_image_in_editor(editor: SmartEditorOne, page: Page):
    loader = AssetLoader()
    if not loader.images:
        pytest.skip("assets/images/ 에 이미지가 없습니다.")
    editor.open()
    editor.execute(ImageStep(path=loader.images[0]))
    assert page.frame_locator(_MAIN_FRAME).first \
        .locator(_EDITOR_SEL.css("editor_image")).first.is_visible()


# ---------------------------------------------------------------------------
# E2E: Representative image
# ---------------------------------------------------------------------------

def _upload_three(editor, page):
    loader = AssetLoader()
    if not loader.images:
        pytest.skip("assets/images/ 에 이미지가 없습니다.")
    editor.open()
    for i in range(3):
        if i > 0:
            editor.move_cursor_to_end()
        editor.execute(ImageStep(path=loader.images[0]))
    page.frame_locator(_MAIN_FRAME).first \
        .locator(_EDITOR_SEL.css("editor_image")).nth(2) \
        .wait_for(state="visible", timeout=15_000)


def _assert_selected(page, index, total):
    frame   = page.frame_locator(_MAIN_FRAME).first
    buttons = frame.locator(_EDITOR_SEL.css("editor_image_rep"))
    assert frame.locator(_EDITOR_SEL.css("editor_image_rep_selected")).count() == 1
    for i in range(total):
        classes = buttons.nth(i).get_attribute("class") or ""
        if i == index:
            assert "se-is-selected" in classes
        else:
            assert "se-is-selected" not in classes


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


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _run_job(job, editor) -> None:
    """
    PostingJob 을 실행한다. 성공 시 None, 실패 시 예외.
    conftest.py 의 ParagraphGenerator mock 으로 Gemini API 호출 없음.
    """
    job.run(editor)


# ---------------------------------------------------------------------------
# Pipeline: text only
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_text_only(editor: SmartEditorOne, account: AccountOption):
    """텍스트 블록만 있는 포스트 — 이미지 불필요."""
    job = (
        PostingJob
        .for_account(account)
        .with_title(TitleOption(fixed_title="텍스트 전용 테스트"))
        .with_body([
            TextBlock(prompt="강남 수학 과외 홍보 블로그"),
            TextBlock(prompt="후기 형식 마무리"),
        ])
        .with_publish(PublishOption(mode="immediate"))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


# ---------------------------------------------------------------------------
# Pipeline: all options
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_all_options(editor: SmartEditorOne, account: AccountOption):
    """
    빌더의 모든 옵션을 지정한 통합 파이프라인 테스트.

    with_title        — template 기반 제목 생성
    with_body         — ImageBlock + TextBlock + FeaturedBlock 혼합
    with_seo          — 키워드·글자수·톤 지정 (TextBlock.prompt 보다 우선)
    with_media        — pixel_jitter / Exif / featured overlay
    with_publish      — 예약 발행 (fixed, +2시간)
    with_setting      — 기본 런타임 설정

    dry_run=True (editor fixture 기본값) — 팝오버 열림 후 발행 버튼 미클릭.
    """
    from datetime import datetime, timedelta
    from automator.options import KST

    now    = datetime.now(tz=KST)
    target = (
        now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        + timedelta(hours=2)
    )

    loader = AssetLoader()
    images = loader.images[:2]
    thumbs = loader.thumbnails[:1]

    body = []
    if images:
        body.append(ImageBlock(path=images[0]))
    body.append(TextBlock(prompt="강남 수학 과외 홍보 블로그"))
    if len(images) > 1:
        body.append(ImageBlock(path=images[1]))
    body.append(TextBlock(prompt="후기 형식 마무리"))
    if thumbs:
        body.append(FeaturedBlock(path=thumbs[0]))

    job = (
        PostingJob
        .for_account(account)
        .with_title(TitleOption(
            template="{region} {subject} {learning_type} {salt}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
        ))
        .with_body(body)
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
        .with_media(MediaOption(
            pixel_jitter              = True,
            size_jitter_px            = 2,
            exif_description          = "강남 수학 과외",
            exif_gps_lat              = 37.4942,
            exif_gps_lng              = 127.0617,
            filename_keyword          = "강남-수학-과외",
            preview_saturation_jitter = 0.03,
            featured_saturation_shift = 0.30,
            featured_overlay_text     = ["강남", "수학 과외"],
            featured_text_color       = "#FFFFFF",
            featured_line_spacing     = 24,
            featured_letter_spacing   = 3,
            upload_delay_ms           = 0,
        ))
        .with_publish(PublishOption(
            mode = "fixed",
            at   = target,
        ))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)


# ---------------------------------------------------------------------------
# Real publish — --real-run 플래그로만 실행
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_pipeline_real_publish(page: Page, account: AccountOption, real_run: bool):
    """
    실제 발행 테스트 — --real-run 플래그 없으면 skip.

    실행 조건:
      - pytest --real-run
      - ENV=production  (Gemini 실제 호출)
      - GEMINI_API_KEY  (.env 설정)
      - assets/images/, assets/thumbnails/ 에 파일 존재
    """
    if not real_run:
        pytest.skip("--real-run 플래그 없음 — 실제 발행 건너뜀")

    from datetime import datetime, timedelta
    from automator.options import KST

    now    = datetime.now(tz=KST)
    target = (
        now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        + timedelta(hours=2)
    )

    loader = AssetLoader()
    body   = loader.default_blocks(prompt="강남 수학 과외 홍보 블로그", n_paragraphs=3)

    write_url = f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&"
    editor    = SmartEditorOne(page, write_url, dry_run=False)

    job = (
        PostingJob
        .for_account(account)
        .with_title(TitleOption(
            template="{region} {subject} {learning_type} {salt}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
        ))
        .with_body(body)
        .with_seo(SEOOption(
            keyword             = "강남 수학 과외",
            keyword_count_first = 3,
            keyword_count_last  = 2,
            tone                = "review_style",
            include_question    = True,
            include_cta         = True,
        ))
        .with_media(MediaOption(
            pixel_jitter              = True,
            size_jitter_px            = 2,
            exif_description          = "강남 수학 과외",
            exif_gps_lat              = 37.4942,
            exif_gps_lng              = 127.0617,
            filename_keyword          = "강남-수학-과외",
            featured_overlay_text     = ["강남", "수학 과외"],
            upload_delay_ms           = 1500,
        ))
        .with_publish(PublishOption(
            mode = "fixed",
            at   = target,
        ))
        .with_setting(RunSetting())
    )
    _run_job(job, editor)
