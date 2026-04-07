"""
tests/unit/automator/test_ai_section.py
-----------------------------------------
AiSectionBlock + AiSectionHandler 통합 테스트.
"""

import pytest
from unittest.mock import MagicMock

from automator.options import (
    AiSectionBlock, HeadingBlock, ListBlock, TextBlock, QuoteBlock,
    DividerBlock,
)
from automator.block_handlers import (
    AiSectionHandler, ContentContext, _build_ai_section_prompt,
)
from automator.editor import (
    HeadingStep, ListStep, TextStep, QuoteStep, DividerStep,
)


# ---------------------------------------------------------------------------
# _build_ai_section_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    def test_basic(self):
        prompt = _build_ai_section_prompt(
            "수학학원의 장점",
            ("heading", "list", "paragraph"),
        )
        assert "수학학원의 장점" in prompt
        assert "## 소제목" in prompt
        assert "글머리 기호" in prompt
        assert "일반 단락" in prompt

    def test_empty_structure_returns_prompt_only(self):
        assert _build_ai_section_prompt("hi", tuple()) == "hi"

    def test_unknown_structure_uses_raw_name(self):
        prompt = _build_ai_section_prompt("hi", ("custom_block",))
        assert "custom_block" in prompt


# ---------------------------------------------------------------------------
# AiSectionHandler — to_steps
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx():
    return ContentContext(text_gen=MagicMock(), img_proc=MagicMock())


class TestAiSectionHandler:

    def test_basic_lenient(self, ctx):
        ctx.text_gen.generate.return_value = (
            "## 장점\n\n- 맞춤 케어\n- 체계적\n\n학원이 중요합니다."
        )
        block = AiSectionBlock(
            prompt="수학학원의 장점",
            structure=("heading", "list", "paragraph"),
        )
        steps = AiSectionHandler().to_steps(block, ctx)
        assert len(steps) == 3
        assert isinstance(steps[0], HeadingStep)
        assert isinstance(steps[1], ListStep)
        assert isinstance(steps[2], TextStep)
        # AI는 1번만 호출
        assert ctx.text_gen.generate.call_count == 1

    def test_auto_prompt_adds_guide(self, ctx):
        ctx.text_gen.generate.return_value = "## h\n\n본문"
        block = AiSectionBlock(
            prompt="기본 프롬프트",
            structure=("heading", "paragraph"),
            auto_prompt=True,
        )
        AiSectionHandler().to_steps(block, ctx)
        called_with = ctx.text_gen.generate.call_args[0][0]
        assert "기본 프롬프트" in called_with
        assert "마크다운으로" in called_with

    def test_auto_prompt_off(self, ctx):
        ctx.text_gen.generate.return_value = "## h\n\n본문"
        block = AiSectionBlock(
            prompt="원본 프롬프트",
            structure=("heading", "paragraph"),
            auto_prompt=False,
        )
        AiSectionHandler().to_steps(block, ctx)
        called_with = ctx.text_gen.generate.call_args[0][0]
        # 가이드 없이 원본만
        assert called_with == "원본 프롬프트"

    def test_strict_match(self, ctx):
        ctx.text_gen.generate.return_value = "## h\n\n- a\n- b\n\n본문"
        block = AiSectionBlock(
            prompt="x",
            structure=("heading", "list", "paragraph"),
            on_mismatch="strict",
        )
        steps = AiSectionHandler().to_steps(block, ctx)
        assert len(steps) == 3

    def test_strict_mismatch_raises(self, ctx):
        # AI가 list를 빼먹음
        ctx.text_gen.generate.return_value = "## h\n\n본문"
        block = AiSectionBlock(
            prompt="x",
            structure=("heading", "list", "paragraph"),
            on_mismatch="strict",
        )
        with pytest.raises(ValueError, match="strict"):
            AiSectionHandler().to_steps(block, ctx)

    def test_lenient_allows_mismatch(self, ctx):
        # AI가 list를 빼먹어도 lenient는 통과
        ctx.text_gen.generate.return_value = "## h\n\n본문"
        block = AiSectionBlock(
            prompt="x",
            structure=("heading", "list", "paragraph"),
            on_mismatch="lenient",
        )
        steps = AiSectionHandler().to_steps(block, ctx)
        assert len(steps) == 2

    def test_empty_response_raises(self, ctx):
        ctx.text_gen.generate.return_value = "   "
        block = AiSectionBlock(prompt="x", structure=("heading",))
        with pytest.raises(ValueError, match="파싱된 블록이 없"):
            AiSectionHandler().to_steps(block, ctx)

    def test_empty_prompt_raises(self, ctx):
        block = AiSectionBlock(prompt="", structure=("heading",))
        with pytest.raises(ValueError, match="prompt"):
            AiSectionHandler().to_steps(block, ctx)

    def test_text_block_uses_textstep_no_extra_call(self, ctx):
        """일반 텍스트는 TextStep으로 변환 — 추가 AI 호출 없음."""
        ctx.text_gen.generate.return_value = "단순 텍스트"
        block = AiSectionBlock(prompt="x", structure=("paragraph",))
        steps = AiSectionHandler().to_steps(block, ctx)
        assert len(steps) == 1
        assert isinstance(steps[0], TextStep)
        # AI 호출 단 1번
        assert ctx.text_gen.generate.call_count == 1

    def test_quote_and_divider_in_response(self, ctx):
        ctx.text_gen.generate.return_value = (
            "> 명언\n\n---\n\n마무리"
        )
        block = AiSectionBlock(
            prompt="x",
            structure=("quote", "divider", "paragraph"),
        )
        steps = AiSectionHandler().to_steps(block, ctx)
        assert len(steps) == 3
        assert isinstance(steps[0], QuoteStep)
        assert isinstance(steps[1], DividerStep)
        assert isinstance(steps[2], TextStep)
