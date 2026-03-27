"""
automator/layout.py
--------------------
Section/Block validation and aggregation utilities.

Public interface
----------------
    all_blocks(sections)          -> list[Block]
    validate_sections(sections)   -> None (raises ValueError)
"""

from __future__ import annotations

from automator.options import (
    Block, Section,
    FeaturedImageBlock,
)


def all_blocks(sections: list[Section]) -> list[Block]:
    """섹션 목록에서 Block 을 순서대로 평탄화해 반환한다."""
    return [block for section in sections for block in section.blocks]


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
