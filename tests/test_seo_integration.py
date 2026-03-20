"""
tests/test_seo_integration.py
----------------------------
ParagraphBlock.keyword 기반 SEO 프롬프트 자동 생성 검증.

- keyword 가 있으면 build_prompt() 가 호출된다.
- keyword 가 없으면 block.prompt 가 그대로 generate_paragraphs() 에 전달된다.
- tone / min_chars / max_chars 가 프롬프트에 반영된다.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption, ParagraphBlock, Section,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return (
        PostingJob.for_account(_account())
        .with_title(TitleOption(fixed_title="제목"))
    )


# ---------------------------------------------------------------------------
# build_prompt 경유 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_keyword_set__build_prompt_called(mock_generate_paragraphs):
    """keyword 가 있으면 build_prompt() 를 통한 SEO 프롬프트가 사용된다."""
    editor = MagicMock()
    (
        _base()
        .with_body([Section(blocks=(
            ParagraphBlock(keyword="강남 수학 과외", tone="review"),
        ))])
        .run(editor)
    )
    calls   = mock_generate_paragraphs.call_args_list
    prompt  = calls[0].kwargs.get("prompt") or calls[0].args[0]
    assert "강남 수학 과외" in prompt
    assert "review" in prompt or "경험담" in prompt


@pytest.mark.unit
def test_no_keyword__block_prompt_used_directly(mock_generate_paragraphs):
    """keyword 없으면 block.prompt 가 generate_paragraphs() 에 그대로 전달된다."""
    editor = MagicMock()
    (
        _base()
        .with_body([Section(blocks=(
            ParagraphBlock(prompt="내 직접 프롬프트"),
        ))])
        .run(editor)
    )
    calls  = mock_generate_paragraphs.call_args_list
    prompt = calls[0].kwargs.get("prompt") or calls[0].args[0]
    assert prompt == "내 직접 프롬프트"


@pytest.mark.unit
def test_paragraph_count_matches_blocks(mock_generate_paragraphs):
    """generate_paragraphs() 호출 횟수 = ParagraphBlock 수."""
    editor = MagicMock()
    (
        _base()
        .with_body([Section(blocks=(
            ParagraphBlock(keyword="kw"),
            ParagraphBlock(keyword="kw"),
            ParagraphBlock(keyword="kw"),
        ))])
        .run(editor)
    )
    assert mock_generate_paragraphs.call_count == 3


@pytest.mark.unit
def test_each_block_gets_own_call(mock_generate_paragraphs):
    """Each ParagraphBlock triggers a separate generate_paragraphs() call."""
    editor = MagicMock()
    (
        _base()
        .with_body([Section(blocks=(
            ParagraphBlock(keyword="kw"),
            ParagraphBlock(keyword="kw"),
        ))])
        .run(editor)
    )
    assert mock_generate_paragraphs.call_count == 2
    for c in mock_generate_paragraphs.call_args_list:
        assert c.args[1] == 1


@pytest.mark.unit
def test_min_max_chars_in_prompt(mock_generate_paragraphs):
    """min_chars / max_chars 가 생성된 프롬프트에 반영된다."""
    editor = MagicMock()
    (
        _base()
        .with_body([Section(blocks=(
            ParagraphBlock(keyword="kw", min_chars=200, max_chars=350),
        ))])
        .run(editor)
    )
    calls  = mock_generate_paragraphs.call_args_list
    prompt = calls[0].kwargs.get("prompt") or calls[0].args[0]
    assert "200" in prompt
    assert "350" in prompt
