"""
tests/test_seo_option.py
-------------------------
Unit tests for SEOOption dataclass and to_prompt().
"""

import pytest
from dataclasses import fields
from automator.options import SEOOption
from automator.seo_prompt import to_prompt


# ---------------------------------------------------------------------------
# SEOOption — 기본값 검증
# ---------------------------------------------------------------------------

class TestSEOOptionDefaults:

    def test_keyword_default_empty(self):
        assert SEOOption().keyword == ""

    def test_keyword_count_first_default(self):
        assert SEOOption().keyword_count_first == 3

    def test_keyword_count_others_default(self):
        assert SEOOption().keyword_count_others == 1

    def test_keyword_count_last_default(self):
        assert SEOOption().keyword_count_last == 2

    def test_keyword_position_default(self):
        assert SEOOption().keyword_position == "first_sentence"

    def test_allow_variants_default(self):
        assert SEOOption().allow_variants is True

    def test_related_keywords_default_empty(self):
        assert SEOOption().related_keywords == []

    def test_repeat_title_keyword_default(self):
        assert SEOOption().repeat_title_keyword is True

    def test_first_para_min_default(self):
        assert SEOOption().first_para_min == 250

    def test_first_para_max_default(self):
        assert SEOOption().first_para_max == 400

    def test_other_para_min_default(self):
        assert SEOOption().other_para_min == 150

    def test_other_para_max_default(self):
        assert SEOOption().other_para_max == 350

    def test_total_min_default(self):
        assert SEOOption().total_min == 800

    def test_total_max_default(self):
        assert SEOOption().total_max == 1200

    def test_sentences_per_para_min_default(self):
        assert SEOOption().sentences_per_para_min == 3

    def test_sentences_per_para_max_default(self):
        assert SEOOption().sentences_per_para_max == 7

    def test_sentence_max_chars_default(self):
        assert SEOOption().sentence_max_chars == 60

    def test_sentence_variety_default(self):
        assert SEOOption().sentence_variety is True

    def test_first_sentence_max_default(self):
        assert SEOOption().first_sentence_max == 40

    def test_include_question_default(self):
        assert SEOOption().include_question is True

    def test_tone_default(self):
        assert SEOOption().tone == "review_style"

    def test_include_numbers_default(self):
        assert SEOOption().include_numbers is True

    def test_include_empathy_default(self):
        assert SEOOption().include_empathy is True

    def test_include_cta_default(self):
        assert SEOOption().include_cta is True

    def test_use_connectors_default(self):
        assert SEOOption().use_connectors is True


# ---------------------------------------------------------------------------
# SEOOption — 유효성 검사
# ---------------------------------------------------------------------------

class TestSEOOptionValidation:

    def test_valid_keyword_position_values(self):
        for pos in ("first_sentence", "early", "anywhere"):
            SEOOption(keyword_position=pos)  # 예외 없어야 함

    def test_invalid_keyword_position_raises(self):
        with pytest.raises(ValueError, match="keyword_position"):
            SEOOption(keyword_position="invalid")

    def test_valid_tone_values(self):
        for tone in ("formal", "informal_friendly", "review_style"):
            SEOOption(tone=tone)

    def test_invalid_tone_raises(self):
        with pytest.raises(ValueError, match="tone"):
            SEOOption(tone="casual")

    def test_first_para_min_less_than_max(self):
        with pytest.raises(ValueError, match="first_para"):
            SEOOption(first_para_min=400, first_para_max=200)

    def test_other_para_min_less_than_max(self):
        with pytest.raises(ValueError, match="other_para"):
            SEOOption(other_para_min=400, other_para_max=200)

    def test_total_min_less_than_max(self):
        with pytest.raises(ValueError, match="total"):
            SEOOption(total_min=1500, total_max=800)

    def test_sentences_per_para_min_less_than_max(self):
        with pytest.raises(ValueError, match="sentences_per_para"):
            SEOOption(sentences_per_para_min=8, sentences_per_para_max=3)

    def test_keyword_count_non_negative(self):
        with pytest.raises(ValueError, match="keyword_count"):
            SEOOption(keyword_count_first=-1)


# ---------------------------------------------------------------------------
# to_prompt() — 단락 인덱스별 프롬프트 생성
# ---------------------------------------------------------------------------

class TestToPrompt:

    def _seo(self, **kwargs):
        return SEOOption(keyword="강남 수학 과외", **kwargs)

    def test_first_para_uses_keyword_count_first(self):
        seo    = self._seo(keyword_count_first=3)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "3회" in prompt

    def test_middle_para_uses_keyword_count_others(self):
        seo    = self._seo(keyword_count_others=1)
        prompt = to_prompt(seo, paragraph_index=1, total_paragraphs=3)
        assert "1회" in prompt

    def test_last_para_uses_keyword_count_last(self):
        seo    = self._seo(keyword_count_last=2)
        prompt = to_prompt(seo, paragraph_index=2, total_paragraphs=3)
        assert "2회" in prompt

    def test_first_para_char_range(self):
        seo    = self._seo(first_para_min=250, first_para_max=400)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "250" in prompt and "400" in prompt

    def test_other_para_char_range(self):
        seo    = self._seo(other_para_min=150, other_para_max=350)
        prompt = to_prompt(seo, paragraph_index=1, total_paragraphs=3)
        assert "150" in prompt and "350" in prompt

    def test_keyword_in_prompt(self):
        seo    = self._seo()
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "강남 수학 과외" in prompt

    def test_first_sentence_max_in_first_para(self):
        seo    = self._seo(first_sentence_max=40)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "40" in prompt

    def test_first_sentence_max_not_in_other_para(self):
        seo    = self._seo(first_sentence_max=40)
        prompt = to_prompt(seo, paragraph_index=1, total_paragraphs=3)
        # 첫 문장 길이 제약은 첫 단락에만 적용
        assert "첫 문장" not in prompt

    def test_question_in_first_para_when_enabled(self):
        seo    = self._seo(include_question=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "질문" in prompt

    def test_no_question_when_disabled(self):
        seo    = self._seo(include_question=False)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "질문" not in prompt

    def test_cta_in_last_para_when_enabled(self):
        seo    = self._seo(include_cta=True)
        prompt = to_prompt(seo, paragraph_index=2, total_paragraphs=3)
        assert "CTA" in prompt or "행동" in prompt or "댓글" in prompt

    def test_no_cta_in_middle_para(self):
        seo    = self._seo(include_cta=True)
        prompt = to_prompt(seo, paragraph_index=1, total_paragraphs=3)
        assert "CTA" not in prompt

    def test_related_keywords_in_prompt_when_set(self):
        seo    = self._seo(related_keywords=["대치동", "내신"])
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "대치동" in prompt or "내신" in prompt

    def test_allow_variants_mentions_variant(self):
        seo    = self._seo(allow_variants=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "변형" in prompt or "혼용" in prompt

    def test_tone_in_prompt(self):
        for tone in ("formal", "informal_friendly", "review_style"):
            seo    = self._seo(tone=tone)
            prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
            assert len(prompt) > 0  # 톤이 어떤 형태로든 반영됨

    def test_numbers_instruction_when_enabled(self):
        seo    = self._seo(include_numbers=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "수치" in prompt or "숫자" in prompt

    def test_empathy_instruction_when_enabled(self):
        seo    = self._seo(include_empathy=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "공감" in prompt

    def test_cta_disabled_no_cta_in_last(self):
        seo    = self._seo(include_cta=False)
        prompt = to_prompt(seo, paragraph_index=2, total_paragraphs=3)
        assert "댓글" not in prompt and "저장" not in prompt

    def test_sentence_variety_in_prompt(self):
        seo    = self._seo(sentence_variety=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "다양" in prompt or "길이" in prompt

    def test_sentence_max_chars_in_prompt(self):
        seo    = self._seo(sentence_max_chars=60)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
        assert "60" in prompt

    def test_connector_instruction_when_enabled(self):
        seo    = self._seo(use_connectors=True)
        prompt = to_prompt(seo, paragraph_index=1, total_paragraphs=3)
        assert "연결" in prompt or "흐름" in prompt

    def test_returns_string(self):
        prompt = to_prompt(self._seo(), paragraph_index=0, total_paragraphs=3)
        assert isinstance(prompt, str) and len(prompt) > 50

    def test_single_paragraph_uses_both_first_and_last_rules(self):
        """단락이 1개면 첫 단락이자 마지막 단락 — 양쪽 규칙 모두 적용"""
        seo    = self._seo(keyword_count_first=3, keyword_count_last=2,
                           include_question=True, include_cta=True)
        prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=1)
        assert "3회" in prompt  # first 규칙
        assert "질문" in prompt  # first 규칙
        assert "댓글" in prompt or "저장" in prompt  # last 규칙
