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
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page

from automator.config import browser_settings
from automator.options import (
    AccountOption, TitleOption, KST,
    ParagraphBlock, ImageBlock, FeaturedImageBlock, Section,
    PublishOption,
)
from automator.selector_loader import SelectorLoader
from automator.smart_editor import SmartEditorOne
from automator.contracts import PostingSpec
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.gemini_generator import GeminiGenerator
from automator.local_processor import LocalImageProcessor
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder
from automator.runner import JobRunner

load_dotenv()

NAVER_ID      = os.getenv("NAVER_ID", "")
NAVER_PW      = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
SESSION_PATH  = os.getenv("SESSION_PATH", "session_state.json")

_MAIN_FRAME  = "#mainFrame"
_EDITOR_BODY = ".se-content"

_LOGIN_SEL  = SelectorLoader.load("selectors/naver/login.json")
_EDITOR_SEL = SelectorLoader.load("selectors/naver/editor.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _asset(subdir: str, index: int) -> str | None:
    """assets/<subdir>/ 의 index 번째 파일 경로. 없으면 None."""
    base  = Path("assets") / subdir
    files = sorted(base.iterdir()) if base.is_dir() else []
    return str(files[index]) if index < len(files) else None


def _make_runner(real: bool = False) -> JobRunner:
    """Build a JobRunner with stubs (default) or real implementations."""
    if real:
        text_gen = GeminiGenerator()
        img_proc = LocalImageProcessor()
    else:
        text_gen = StubTextGenerator()
        img_proc = NoopImageProcessor()
    return JobRunner(SpecValidator(), ContentBuilder(text_gen, img_proc))


def _run_spec(spec: PostingSpec, editor, *, real: bool = False) -> None:
    """Execute a PostingSpec through the runner."""
    runner = _make_runner(real=real)
    runner.run(spec, editor)


def _schedule(hours_ahead: int = 2) -> datetime:
    """현재 시각 기준 hours_ahead 시간 뒤 정각(10분 단위)을 반환한다."""
    now = datetime.now(tz=KST)
    return (
        now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
        + timedelta(hours=hours_ahead)
    )


# ---------------------------------------------------------------------------
# E2E: Editor loads
# ---------------------------------------------------------------------------

def test_editor_iframe_is_visible(page: Page, account: AccountOption):
    page.goto(f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&")
    page.frame_locator(_MAIN_FRAME) \
        .locator(_EDITOR_BODY) \
        .wait_for(state="visible", timeout=15_000)


# ---------------------------------------------------------------------------
# Pipeline: text only
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_text_only(editor: SmartEditorOne, account: AccountOption):
    """텍스트 블록만 있는 포스트 — 이미지 불필요."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="텍스트 전용 테스트"),
        body=(Section(blocks=(
            ParagraphBlock(prompt="강남 수학 과외 홍보 블로그"),
            ParagraphBlock(prompt="후기 형식 마무리"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


# ---------------------------------------------------------------------------
# Pipeline: all options (dry_run)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_all_options(editor: SmartEditorOne, account: AccountOption):
    """
    모든 옵션을 지정한 통합 파이프라인 테스트.
    dry_run=True (editor fixture 기본값) — 팝오버 열림 후 발행 버튼 미클릭.
    이미지는 assets/ 에 파일이 있을 때만 포함한다.
    """
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)

    blocks: list = [
        ParagraphBlock(
            prompt="강남 수학 과외 홍보 블로그",
            keyword="강남 수학 과외",
            tone="review",
        ),
        ParagraphBlock(prompt="후기 형식 마무리"),
    ]
    if image:
        blocks.insert(0, ImageBlock(path=image))
    if thumb:
        blocks.append(FeaturedImageBlock(
            path=thumb,
            overlay_text="강남 수학 과외",
        ))

    spec = PostingSpec(
        account=account,
        title=TitleOption(
            template="{region} {subject} {learning_type} {salt_suffix}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
            pools={"salt_suffix": ("강력 추천", "즉시 가능")},
        ),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="fixed", at=_schedule()),
    )
    _run_spec(spec, editor)


# ---------------------------------------------------------------------------
# Real publish — --real-run 플래그로만 실행
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_real_publish(page: Page, account: AccountOption, real_run: bool):
    """
    실제 발행 테스트 — --real-run 플래그 없으면 skip.

    실행 조건:
      - pytest --real-run
      - ENV=production  (Gemini 실제 호출)
      - GEMINI_API_KEY  (.env 설정)
    """
    if not real_run:
        pytest.skip("--real-run 플래그 없음 — 실제 발행 건너뜀")

    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)

    blocks: list = [
        ParagraphBlock(keyword="강남 수학 과외", tone="review",
                       min_chars=250, max_chars=400),
        ParagraphBlock(keyword="강남 수학 과외", tone="review"),
        ParagraphBlock(keyword="강남 수학 과외", tone="promotional"),
    ]
    if image:
        blocks.insert(0, ImageBlock(path=image))
    if thumb:
        blocks.append(FeaturedImageBlock(
            path=thumb,
            overlay_text="강남 수학 과외",
        ))

    write_url = f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&"
    editor    = SmartEditorOne(page, write_url, dry_run=False)

    spec = PostingSpec(
        account=account,
        title=TitleOption(
            template="{region} {subject} {learning_type} {salt_suffix}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
            pools={"salt_suffix": ("강력 추천", "즉시 가능")},
        ),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="fixed", at=_schedule()),
    )
    _run_spec(spec, editor, real=True)
