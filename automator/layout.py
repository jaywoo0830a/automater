"""
automator/layout.py
--------------------
Block 목록 유효성 검사 및 집계 유틸리티.

Block 순서가 곧 레이아웃이다.
Block 순서가 곧 레이아웃이다.
"""

from __future__ import annotations

from automator.options import Block, TextBlock, ImageBlock, FeaturedBlock


def text_block_count(blocks: list[Block]) -> int:
    """TextBlock 의 수를 반환한다."""
    return sum(1 for b in blocks if isinstance(b, TextBlock))


def validate_blocks(blocks: list[Block]) -> None:
    """
    Block 목록의 유효성을 검사한다.

    Raises:
        ValueError: FeaturedBlock 이 2개 이상인 경우.
                    (대표 이미지는 하나여야 한다.)
    """
    featured = [b for b in blocks if isinstance(b, FeaturedBlock)]
    if len(featured) > 1:
        raise ValueError(
            f"FeaturedBlock 은 최대 1개여야 합니다. "
            f"현재 {len(featured)}개가 있습니다."
        )
