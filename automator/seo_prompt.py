"""
automator/seo_prompt.py
------------------------
ParagraphBlock 의 keyword / tone / min_chars / max_chars 를 바탕으로
Gemini 에 전달할 SEO 최적화 프롬프트를 자동 생성한다.

Usage:
    from automator.options import ParagraphBlock
    from automator.seo_prompt import build_prompt

    block  = ParagraphBlock(keyword="강남 수학 과외", tone="review", min_chars=250)
    prompt = build_prompt(block, paragraph_index=0, total_paragraphs=3)
"""

from __future__ import annotations

from automator.options import ParagraphBlock

_TONE_LABELS = {
    "informational": "정보 전달 위주의 명확한 어조",
    "review":        "실제 학부모가 쓴 경험담 형식, 1인칭 시점",
    "story":         "이야기 형식, 감성적인 흐름",
    "promotional":   "홍보·설득 어조, 행동 유도 포함",
}

_POSITION_LABELS = {
    0: "첫 문장 안에",     # 첫 번째 단락
    "mid": "단락 앞부분(첫 30%) 안에",
    "last": "자연스럽게 1회 이상",
}


def build_prompt(
    block:            ParagraphBlock,
    paragraph_index:  int,
    total_paragraphs: int,
) -> str:
    """
    ParagraphBlock 의 메타 정보로 SEO 프롬프트를 생성한다.

    keyword 가 없으면 block.prompt 를 그대로 반환한다.

    Args:
        block:            ParagraphBlock 인스턴스.
        paragraph_index:  0-based 현재 단락 인덱스.
        total_paragraphs: 전체 단락 수.

    Returns:
        Gemini 에 전달할 프롬프트 문자열.
    """
    if not block.keyword:
        return block.prompt

    keyword   = block.keyword
    tone_desc = _TONE_LABELS.get(block.tone, block.tone)

    # 위치별 키워드 배치 지침
    if paragraph_index == 0:
        position_desc = _POSITION_LABELS[0]
        kw_count      = 3
    elif paragraph_index == total_paragraphs - 1:
        position_desc = _POSITION_LABELS["last"]
        kw_count      = 2
    else:
        position_desc = _POSITION_LABELS["mid"]
        kw_count      = 1

    # 글자 수 지침
    if block.min_chars > 0 and block.max_chars > 0:
        length_desc = f"{block.min_chars}자 이상 {block.max_chars}자 이하"
    elif block.min_chars > 0:
        length_desc = f"{block.min_chars}자 이상"
    elif block.max_chars > 0:
        length_desc = f"{block.max_chars}자 이하"
    else:
        length_desc = "150자 이상 400자 이하"

    # 추가 지시사항 (block.prompt 가 있으면 포함)
    extra = f"\n\n추가 지시사항: {block.prompt}" if block.prompt else ""

    return (
        f"다음 조건을 모두 충족하는 블로그 단락을 한국어로 작성하세요.\n\n"
        f"키워드: {keyword}\n"
        f"키워드 위치: {position_desc} {kw_count}회 이상 자연스럽게 포함\n"
        f"문체: {tone_desc}\n"
        f"글자 수: {length_desc}\n"
        f"단락 위치: 전체 {total_paragraphs}개 단락 중 {paragraph_index + 1}번째\n"
        f"주의: 제목, 소제목 없이 본문 단락만 작성하세요.{extra}"
    )
