"""
automator/seo_prompt.py
------------------------
Converts SEOOption into a structured Gemini prompt for a single paragraph.

Usage:
    from automator.options import SEOOption
    from automator.seo_prompt import to_prompt

    seo    = SEOOption(keyword="강남 수학 과외", tone="review_style")
    prompt = to_prompt(seo, paragraph_index=0, total_paragraphs=3)
    # → pass to ParagraphGenerator(prompt=prompt).generate(1)
"""

from __future__ import annotations

from automator.options import SEOOption

_TONE_LABELS = {
    "formal":             "격식체, 전문적인 어조",
    "informal_friendly":  "친근하고 부드러운 구어체",
    "review_style":       "실제 학부모가 쓴 경험담 형식, 1인칭 시점",
}

_POSITION_LABELS = {
    "first_sentence": "첫 문장 안에",
    "early":          "단락 앞부분(첫 30%) 안에",
    "anywhere":       "단락 안 어디든",
}


def to_prompt(
    seo:              SEOOption,
    paragraph_index:  int,
    total_paragraphs: int,
) -> str:
    """
    Build a Gemini instruction string for one paragraph.

    Args:
        seo:              SEOOption instance.
        paragraph_index:  0-based index of this paragraph.
        total_paragraphs: Total number of paragraphs in the post.

    Returns:
        Instruction string — pass directly to ParagraphGenerator(prompt=...).
    """
    is_first = paragraph_index == 0
    is_last  = paragraph_index == total_paragraphs - 1

    # ── Keyword count for this paragraph ─────────────────────────────────────
    if is_first:
        kw_count = seo.keyword_count_first
    elif is_last:
        kw_count = seo.keyword_count_last
    else:
        kw_count = seo.keyword_count_others

    # ── Character range ───────────────────────────────────────────────────────
    if is_first:
        char_min, char_max = seo.first_para_min, seo.first_para_max
    else:
        char_min, char_max = seo.other_para_min, seo.other_para_max

    # ── Keyword instruction ───────────────────────────────────────────────────
    if seo.keyword:
        variant_note = " (띄어쓰기 변형 혼용 가능)" if seo.allow_variants else ""
        position_note = f", 반드시 {_POSITION_LABELS[seo.keyword_position]} 등장" if is_first else ""
        keyword_line = (
            f'- 키워드 "{seo.keyword}"{variant_note}를 정확히 {kw_count}회 포함{position_note}'
        )
    else:
        keyword_line = ""

    # ── Collect conditions ────────────────────────────────────────────────────
    conditions: list[str] = []

    if keyword_line:
        conditions.append(keyword_line)

    conditions.append(f"- {char_min}자 이상 {char_max}자 이하로 작성")
    conditions.append(
        f"- 문장 수: {seo.sentences_per_para_min}~{seo.sentences_per_para_max}개"
    )
    conditions.append(f"- 한 문장의 최대 길이: {seo.sentence_max_chars}자 이하 (모바일 가독성)")

    if seo.sentence_variety:
        conditions.append("- 짧은 문장(~20자)과 긴 문장(~60자)을 혼합해 리듬감을 만들 것")

    if is_first and seo.first_sentence_max:
        conditions.append(f"- 첫 문장은 {seo.first_sentence_max}자 이내로 짧고 명확하게")

    if is_first and seo.include_question:
        conditions.append('- 질문형 문장 1개 포함 (예: "혹시 강남 수학 과외를 찾고 계신가요?")')

    if seo.related_keywords:
        kws = ", ".join(f'"{k}"' for k in seo.related_keywords)
        conditions.append(f"- 연관 키워드 {kws} 중 1~2개를 자연스럽게 포함")

    if seo.include_numbers:
        conditions.append('- 구체적인 수치 포함 (예: "성적 30% 향상", "3개월 만에")')

    if seo.include_empathy:
        conditions.append('- 공감 표현 포함 (예: "많이 고민하셨죠?", "저도 처음엔 몰랐어요")')

    if not is_first and seo.use_connectors:
        conditions.append('- 앞 단락과 자연스럽게 이어지도록 연결 표현 사용 (예: "그런데", "특히", "그래서")')

    if is_last and seo.include_cta:
        conditions.append(
            '- 마지막 문장은 행동 유도(CTA)로 마무리 (예: "댓글로 편하게 물어보세요", "저장해두시면 나중에 도움이 돼요")'
        )

    tone_label = _TONE_LABELS[seo.tone]
    conditions.append(f"- 톤: {tone_label}")

    conditions_str = "\n".join(conditions)

    return f"""다음 조건을 반드시 지켜서 블로그 단락 1개를 작성해주세요.

[조건]
{conditions_str}

[출력 형식]
JSON 배열로만 반환하세요. 다른 설명 없이 배열만: ["단락 내용"]""".strip()
