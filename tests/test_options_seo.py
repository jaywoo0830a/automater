"""
tests/test_options_seo.py
--------------------------
build_prompt() 단위 테스트 — SEO 프롬프트 자동 생성 로직 검증.
"""

import pytest
from automator.options import ParagraphBlock
from automator.seo_prompt import build_prompt


@pytest.mark.unit
def test_no_keyword_returns_prompt_as_is():
    """keyword 없으면 block.prompt 를 그대로 반환한다."""
    block = ParagraphBlock(prompt="내 프롬프트")
    assert build_prompt(block, 0, 3) == "내 프롬프트"


@pytest.mark.unit
def test_keyword_returns_seo_prompt():
    """keyword 가 있으면 SEO 프롬프트가 생성된다."""
    block  = ParagraphBlock(keyword="강남 수학 과외")
    prompt = build_prompt(block, 0, 3)
    assert "강남 수학 과외" in prompt


@pytest.mark.unit
def test_first_paragraph_has_higher_keyword_count():
    """첫 번째 단락은 키워드 횟수가 더 많다."""
    block   = ParagraphBlock(keyword="kw")
    first   = build_prompt(block, 0, 3)
    middle  = build_prompt(block, 1, 3)
    assert "3회" in first
    assert "1회" in middle


@pytest.mark.unit
def test_tone_reflected_in_prompt():
    """tone 이 프롬프트에 반영된다."""
    block  = ParagraphBlock(keyword="kw", tone="review")
    prompt = build_prompt(block, 0, 3)
    assert "경험담" in prompt or "review" in prompt


@pytest.mark.unit
def test_min_max_chars_reflected_in_prompt():
    """min_chars / max_chars 가 프롬프트에 반영된다."""
    block  = ParagraphBlock(keyword="kw", min_chars=250, max_chars=400)
    prompt = build_prompt(block, 0, 3)
    assert "250" in prompt
    assert "400" in prompt


@pytest.mark.unit
def test_only_min_chars():
    block  = ParagraphBlock(keyword="kw", min_chars=300)
    prompt = build_prompt(block, 0, 3)
    assert "300" in prompt


@pytest.mark.unit
def test_extra_prompt_appended_when_both_keyword_and_prompt():
    """keyword 와 prompt 가 함께 있으면 prompt 가 추가 지시사항으로 포함된다."""
    block  = ParagraphBlock(keyword="kw", prompt="추가 지시")
    prompt = build_prompt(block, 0, 3)
    assert "추가 지시" in prompt
    assert "kw" in prompt
