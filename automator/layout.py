"""
automator/layout.py
--------------------
Section / Block 유효성 검사 및 집계 유틸리티.

Section 이 최상위 단위다. 모든 Block 은 Section 안에 있다.
"""

from __future__ import annotations

from automator.options import (
    Block, Section,
    ParagraphBlock, FeaturedImageBlock,
)


def all_blocks(sections: list[Section]) -> list[Block]:
    """섹션 목록에서 Block 을 순서대로 평탄화해 반환한다."""
    return [block for section in sections for block in section.blocks]


def paragraph_block_count(sections: list[Section]) -> int:
    """전체 섹션에서 ParagraphBlock 의 수를 반환한다."""
    return sum(1 for b in all_blocks(sections) if isinstance(b, ParagraphBlock))


def validate_sections(sections: list[Section]) -> None:
    """
    Section 목록의 유효성을 검사한다.

    Raises:
        ValueError: FeaturedImageBlock 이 2개 이상인 경우.
    """
    featured = [b for b in all_blocks(sections) if isinstance(b, FeaturedImageBlock)]
    if len(featured) > 1:
        raise ValueError(
            f"FeaturedImageBlock 은 최대 1개여야 합니다. "
            f"현재 {len(featured)}개가 있습니다."
        )
