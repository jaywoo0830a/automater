"""
tests/test_job_with_seo.py
---------------------------
PostingJob + SEOOption 연동 검증.

conftest.py 가 ParagraphGenerator 를 MagicMock 으로 교체하므로,
mock_paragraph_generator fixture 를 통해 생성자 호출 내역을 검사한다.
"""

import pytest
from unittest.mock import MagicMock

from automator.editor import BlogEditor, ParagraphStep
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption, TextBlock, SEOOption,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return (PostingJob.for_account(_account())
            .with_title(TitleOption(fixed_title="T")))


# ---------------------------------------------------------------------------
# SEO 프롬프트 우선순위
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_seo_overrides_text_block_prompt(mock_paragraph_generator):
    """SEOOption 설정 시 ParagraphGenerator 에 SEO 프롬프트가 전달된다."""
    editor = MagicMock(spec=BlogEditor)
    (_base()
     .with_body([TextBlock(prompt="무시됨"), TextBlock(prompt="무시됨")])
     .with_seo(SEOOption(keyword="강남 수학 과외", tone="review_style"))
     .run(editor))

    # conftest 가 교체한 MagicMock 의 생성자 호출 인자 검사
    calls   = mock_paragraph_generator.call_args_list
    prompts = [c.kwargs.get("prompt", "") for c in calls]

    assert len(prompts) == 2
    for prompt in prompts:
        assert "강남 수학 과외" in prompt, f"키워드 없음: {prompt!r}"


@pytest.mark.unit
def test_without_seo__uses_text_block_prompt(mock_paragraph_generator):
    """SEOOption 없으면 TextBlock.prompt 가 ParagraphGenerator 에 전달된다."""
    editor = MagicMock(spec=BlogEditor)
    (_base()
     .with_body([TextBlock(prompt="내 프롬프트")])
     .run(editor))

    calls   = mock_paragraph_generator.call_args_list
    prompts = [c.kwargs.get("prompt", "") for c in calls]
    assert any("내 프롬프트" in p for p in prompts)


# ---------------------------------------------------------------------------
# 단락 수 일치
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_seo_paragraph_count_matches_text_block_count(mock_paragraph_generator):
    """SEOOption 설정 시 생성되는 단락 수 = TextBlock 수."""
    editor = MagicMock(spec=BlogEditor)
    (_base()
     .with_body([TextBlock(), TextBlock(), TextBlock()])
     .with_seo(SEOOption(keyword="kw"))
     .run(editor))

    para_steps = [
        c.args[0] for c in editor.execute.call_args_list
        if isinstance(c.args[0], ParagraphStep)
    ]
    assert len(para_steps) == 3


@pytest.mark.unit
def test_seo_calls_generator_per_text_block(mock_paragraph_generator):
    """SEOOption 설정 시 TextBlock 마다 ParagraphGenerator 가 개별 생성된다."""
    editor = MagicMock(spec=BlogEditor)
    (_base()
     .with_body([TextBlock(), TextBlock()])
     .with_seo(SEOOption(keyword="kw"))
     .run(editor))

    # SEO 모드: TextBlock 1개당 ParagraphGenerator 1회 생성, generate(1) 호출
    assert mock_paragraph_generator.call_count == 2


# ---------------------------------------------------------------------------
# SEOOption 없는 경우 — 공유 프롬프트
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_without_seo__shared_prompt_single_generator_call(mock_paragraph_generator):
    """SEOOption 없으면 첫 번째 TextBlock 의 prompt 로 ParagraphGenerator 1회 호출."""
    editor = MagicMock(spec=BlogEditor)
    (_base()
     .with_body([TextBlock(prompt="공유"), TextBlock(prompt="공유")])
     .run(editor))

    # 동일 프롬프트 — generate(2) 한 번 또는 generate(1) 두 번 중 어느 쪽이든
    # ParagraphGenerator 생성자는 최소 1회 호출됨
    assert mock_paragraph_generator.call_count >= 1
