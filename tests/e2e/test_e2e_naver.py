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
    HeadingBlock, ParagraphBlock, ImageBlock, FeaturedImageBlock,
    QuoteBlock, DividerBlock, Section,
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
# Pipeline: heading — all levels
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("level,size", [
    (1, 38), (2, 34), (3, 30), (4, 28), (5, 24), (6, 19),
])
def test_pipeline_heading_level(editor: SmartEditorOne, account: AccountOption, level: int, size: int):
    """H1~H6 각 레벨별 소제목 삽입 — 서식 적용 + 일반 단락 복귀."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title=f"H{level} 소제목 테스트 (size {size})"),
        body=(Section(blocks=(
            HeadingBlock(level=level, text=f"H{level} 소제목 — 크기 {size}"),
            ParagraphBlock(prompt=f"H{level} 아래 일반 본문"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_heading_mixed_levels(editor: SmartEditorOne, account: AccountOption):
    """H1 + H3 + H5 혼합 — 서로 다른 크기가 순서대로 적용되는지 확인."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="혼합 소제목 테스트"),
        body=(Section(blocks=(
            HeadingBlock(level=1, text="대제목 (H1, 38)"),
            ParagraphBlock(prompt="대제목 아래 본문"),
            HeadingBlock(level=3, text="소제목 (H3, 30)"),
            ParagraphBlock(prompt="소제목 아래 본문"),
            HeadingBlock(level=5, text="작은 제목 (H5, 24)"),
            ParagraphBlock(prompt="작은 제목 아래 본문"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_heading_with_image(editor: SmartEditorOne, account: AccountOption):
    """소제목 + 이미지 + 본문 — 이미지 업로드 후 소제목이 깨지지 않는지 확인."""
    image = _asset("images", 0)
    blocks: list = [
        HeadingBlock(level=2, text="이미지 포함 소제목 (H2, 34)"),
        ParagraphBlock(prompt="이미지 위 본문"),
    ]
    if image:
        blocks.insert(1, ImageBlock(path=image))

    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="소제목 + 이미지 테스트"),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


# ---------------------------------------------------------------------------
# Pipeline: quote
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_quote_only(editor: SmartEditorOne, account: AccountOption):
    """인용구만 삽입 — 인용구 서식 적용 + 다음 단락으로 빠져나오는지 확인."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="인용구 테스트"),
        body=(Section(blocks=(
            QuoteBlock(text="교육의 목적은 시험이 아니다"),
            ParagraphBlock(prompt="인용구 아래 일반 본문"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_quote_with_heading(editor: SmartEditorOne, account: AccountOption):
    """소제목 + 본문 + 인용구 + 본문 — 혼합 레이아웃."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="소제목 + 인용구 혼합 테스트"),
        body=(Section(blocks=(
            HeadingBlock(level=2, text="명언 모음"),
            ParagraphBlock(prompt="명언을 소개하는 도입부"),
            QuoteBlock(text="여행은 살아있는 교육이다"),
            ParagraphBlock(prompt="명언에 대한 감상을 작성해줘"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_multiple_quotes(editor: SmartEditorOne, account: AccountOption):
    """인용구 2개 연속 — 각각 독립적으로 서식이 적용되는지 확인."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="연속 인용구 테스트"),
        body=(Section(blocks=(
            QuoteBlock(text="첫 번째 인용구"),
            QuoteBlock(text="두 번째 인용구"),
            ParagraphBlock(prompt="인용구 아래 마무리 본문"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


# ---------------------------------------------------------------------------
# Pipeline: divider
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_divider_between_paragraphs(editor: SmartEditorOne, account: AccountOption):
    """본문 + 구분선 + 본문 — 구분선이 삽입되고 다음 단락이 정상 입력되는지 확인."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="구분선 테스트"),
        body=(Section(blocks=(
            ParagraphBlock(prompt="구분선 위 본문"),
            DividerBlock(),
            ParagraphBlock(prompt="구분선 아래 본문"),
        )),),
        publish=PublishOption(mode="immediate"),
    )
    _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_divider_with_heading_and_quote(editor: SmartEditorOne, account: AccountOption):
    """소제목 + 본문 + 구분선 + 인용구 — 전체 레이아웃 혼합."""
    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="혼합 레이아웃 테스트"),
        body=(Section(blocks=(
            HeadingBlock(level=2, text="첫 번째 섹션"),
            ParagraphBlock(prompt="첫 번째 본문"),
            DividerBlock(),
            QuoteBlock(text="섹션 사이 인용구"),
            DividerBlock(),
            HeadingBlock(level=3, text="두 번째 섹션"),
            ParagraphBlock(prompt="두 번째 본문"),
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
            template="{keyword:region} {keyword:subject} {keyword:learning_type} {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
            pools={"salt_suffix": ("강력 추천", "즉시 가능")},
        ),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="scheduled", at=_schedule()),
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
            template="{keyword:region} {keyword:subject} {keyword:learning_type} {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학", "learning_type": "과외"},
            pools={"salt_suffix": ("강력 추천", "즉시 가능")},
        ),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="scheduled", at=_schedule()),
    )
    _run_spec(spec, editor, real=True)


# ---------------------------------------------------------------------------
# DSL pipeline — CLI config → PostingSpec → editor
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_dsl_full_blocks(editor: SmartEditorOne, account: AccountOption):
    """
    DSL-style post: image + divider + thumbnail + divider + quote + paragraph.

    Mimics a real campaign YAML config. dry_run=True — popover opens but
    confirm is skipped.
    """
    image = _asset("images", 0)
    thumb = _asset("thumbnails", 0)

    blocks: list = [
        ParagraphBlock(prompt="강남 중등 수학과외를 홍보하는 블로그 글"),
    ]
    if image:
        blocks.insert(0, ImageBlock(path=image))
        blocks.insert(1, DividerBlock())
    if thumb:
        blocks.append(DividerBlock())
        blocks.append(FeaturedImageBlock(
            path=thumb,
            overlay_text="강남 수학과외",
            overlay_background=0.5,
            overlay_position="bottom",
        ))
    blocks.append(QuoteBlock(text="강남 중등 수학과외 즉시 가능"))

    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="DSL 풀블록 E2E 테스트"),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="scheduled", at=_schedule()),
    )
    _run_spec(spec, editor)


# ---------------------------------------------------------------------------
# Consecutive posts — same editor, 2 posts back-to-back
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_consecutive_scheduled(editor: SmartEditorOne, account: AccountOption):
    """
    Two posts on the same editor instance — verifies cursor restoration
    after set_representative_media and publish popover flow.

    dry_run=True — popover opens but confirm is skipped.
    """
    thumb = _asset("thumbnails", 0)
    schedule = _schedule()

    for i in range(2):
        blocks: list = [
            ParagraphBlock(prompt=f"연속 발행 테스트 #{i+1}"),
        ]
        if thumb:
            blocks.append(FeaturedImageBlock(
                path=thumb,
                overlay_text=f"테스트 #{i+1}",
                overlay_background=0.4,
                overlay_position="bottom",
            ))

        spec = PostingSpec(
            account=account,
            title=TitleOption(fixed_title=f"연속 발행 E2E #{i+1}"),
            body=(Section(blocks=tuple(blocks)),),
            publish=PublishOption(mode="scheduled", at=schedule),
        )
        _run_spec(spec, editor)


@pytest.mark.slow
def test_pipeline_consecutive_real_publish(
    page: Page, account: AccountOption, real_run: bool,
):
    """
    Two real scheduled posts back-to-back — --real-run flag required.

    Verifies:
        - _wait_for_publish_complete() lets page transition finish
        - editor.open() reloads cleanly for the second post
        - set_representative_media() restores cursor to body
        - publish trigger opens on both posts
    """
    if not real_run:
        pytest.skip("--real-run 플래그 없음")

    thumb = _asset("thumbnails", 0)
    schedule = _schedule()

    write_url = f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&"
    editor    = SmartEditorOne(page, write_url, dry_run=False)

    for i in range(2):
        blocks: list = [
            ParagraphBlock(prompt=f"연속 실발행 테스트 #{i+1}"),
        ]
        if thumb:
            blocks.append(FeaturedImageBlock(
                path=thumb,
                overlay_text=f"실발행 #{i+1}",
                overlay_background=0.5,
                overlay_position="bottom",
            ))

        spec = PostingSpec(
            account=account,
            title=TitleOption(fixed_title=f"연속 실발행 E2E #{i+1}"),
            body=(Section(blocks=tuple(blocks)),),
            publish=PublishOption(mode="scheduled", at=schedule),
        )
        _run_spec(spec, editor, real=True)



# ---------------------------------------------------------------------------
# Long paragraph — real Gemini API → browser rendering
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_pipeline_long_paragraph_real_gemini(
    page: Page, account: AccountOption, real_run: bool,
):
    """
    Real Gemini API → 3500+ char response → browser rendering.

    --real-run required. Calls Gemini with the exact DSL prompt,
    then types the full response into the editor and publishes.
    """
    if not real_run:
        pytest.skip("--real-run 플래그 없음")

    thumb = _asset("thumbnails", 0)

    blocks: list = []
    if thumb:
        blocks.append(FeaturedImageBlock(
            path=thumb,
            overlay_text="강남 수학과외",
            overlay_background=0.5,
            overlay_position="bottom",
        ))
        blocks.append(DividerBlock())
    blocks.append(QuoteBlock(text="강남 중등 수학과외 즉시 가능"))
    blocks.append(ParagraphBlock(
        prompt=(
            "블로그에 글을 적을 껀데 학생의 성향별 수학과외의 후기 형식의 "
            "긴 글이 필요해요. 조건이 있어요. 먼저, 글 초반에는 "
            "강남 중등 수학과외라는 문구가 모두 합쳐서 4번 이상 들어가야 해요. "
            "그리고 글의 길이는 딱 3500자가 필요해요. "
            "글의 톤은 친절하고 따뜻한 느낌이었으면 좋겠습니다."
        ),
    ))

    write_url = f"https://blog.naver.com/{account.meta['blog_id']}?Redirect=Write&"
    editor    = SmartEditorOne(page, write_url, dry_run=False)

    spec = PostingSpec(
        account=account,
        title=TitleOption(fixed_title="Gemini 장문 E2E 실발행"),
        body=(Section(blocks=tuple(blocks)),),
        publish=PublishOption(mode="scheduled", at=_schedule()),
    )
    _run_spec(spec, editor, real=True)
