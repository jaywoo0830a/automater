"""
automator/markdown_parser.py
------------------------------
마크다운 텍스트를 Block 리스트로 파싱한다.

ai_section 블록의 AI 응답을 처리하기 위한 단순 파서.
표준 마크다운 전체를 지원하지 않고, 블로그 글 작성에 필요한
핵심 요소만 다룬다.

지원 요소
---------
    # ~ ######  → HeadingBlock(level=1~6)
    - / *       → ListBlock(ordered=False)
    1. 2. 3.    → ListBlock(ordered=True)
    >           → QuoteBlock
    ---/***/___ → DividerBlock
    그 외 텍스트 → TextBlock (이미 AI가 생성한 결과물)

특징
----
- 인접한 list 항목은 하나의 ListBlock으로 묶인다
- 인접한 텍스트 줄은 하나의 TextBlock으로 묶인다 (빈 줄로 분리)
- 코드 펜스(```)는 단순 텍스트로 처리
- 인라인 마크다운(**bold**, *italic*, [link]())은 그대로 텍스트에 보존
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from automator.options import (
    Block,
    HeadingBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
    TextBlock,
)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_UNORDERED_RE = re.compile(r"^[-*+]\s+(.+)$")
_ORDERED_RE = re.compile(r"^\d+\.\s+(.+)$")
_QUOTE_RE = re.compile(r"^>\s*(.*)$")
_DIVIDER_RE = re.compile(r"^[-*_]{3,}$")
_FENCE_RE = re.compile(r"^```")


def parse_markdown(text: str) -> list[Block]:
    """마크다운 문자열을 Block 리스트로 변환한다.

    Args:
        text: 마크다운 텍스트.

    Returns:
        Block 리스트. 빈 입력이면 빈 리스트 반환.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    in_fence = False
    fence_buf: list[str] = []

    while i < len(lines):
        line = lines[i]

        # 코드 펜스 — 내용은 텍스트로 누적
        if _FENCE_RE.match(line):
            if in_fence:
                # 펜스 종료 — 누적된 내용을 TextBlock으로
                if fence_buf:
                    blocks.append(TextBlock(content="\n".join(fence_buf)))
                    fence_buf = []
                in_fence = False
            else:
                in_fence = True
            i += 1
            continue

        if in_fence:
            fence_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        # 빈 줄 — 스킵
        if not stripped:
            i += 1
            continue

        # 구분선
        if _DIVIDER_RE.match(stripped):
            blocks.append(DividerBlock())
            i += 1
            continue

        # 헤딩
        m = _HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            text_content = m.group(2).strip()
            if text_content:
                blocks.append(HeadingBlock(level=level, text=text_content))
            i += 1
            continue

        # 인용구 — 인접한 > 줄들을 하나로 묶음
        if _QUOTE_RE.match(stripped):
            quote_lines, i = _collect_quote(lines, i)
            if quote_lines:
                blocks.append(QuoteBlock(text="\n".join(quote_lines)))
            continue

        # 순서 없는 리스트
        if _UNORDERED_RE.match(stripped):
            items, i = _collect_list(lines, i, ordered=False)
            if items:
                blocks.append(ListBlock(items=tuple(items), ordered=False))
            continue

        # 순서 있는 리스트
        if _ORDERED_RE.match(stripped):
            items, i = _collect_list(lines, i, ordered=True)
            if items:
                blocks.append(ListBlock(items=tuple(items), ordered=True))
            continue

        # 일반 텍스트 — 인접한 텍스트 줄을 빈 줄까지 묶음
        text_lines, i = _collect_text(lines, i)
        if text_lines:
            blocks.append(TextBlock(content="\n".join(text_lines)))

    # 닫히지 않은 펜스 — 누적분도 텍스트로 보존
    if fence_buf:
        blocks.append(TextBlock(content="\n".join(fence_buf)))

    return blocks


def _collect_quote(lines: list[str], start: int) -> tuple[list[str], int]:
    """인접한 > 라인들을 수집."""
    out: list[str] = []
    i = start
    while i < len(lines):
        m = _QUOTE_RE.match(lines[i].strip())
        if not m:
            break
        content = m.group(1).strip()
        if content:
            out.append(content)
        i += 1
    return out, i


def _collect_list(lines: list[str], start: int, ordered: bool) -> tuple[list[str], int]:
    """인접한 리스트 항목 수집. 같은 종류만."""
    out: list[str] = []
    i = start
    pattern = _ORDERED_RE if ordered else _UNORDERED_RE
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            # 빈 줄 — 리스트 종료
            i += 1
            break
        m = pattern.match(stripped)
        if not m:
            break
        item = m.group(1).strip()
        if item:
            out.append(item)
        i += 1
    return out, i


def _collect_text(lines: list[str], start: int) -> tuple[list[str], int]:
    """인접한 일반 텍스트 라인을 빈 줄/특수 라인 전까지 수집."""
    out: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 빈 줄에서 종료
        if not stripped:
            i += 1
            break

        # 특수 라인 만나면 종료
        if (_HEADING_RE.match(stripped)
            or _UNORDERED_RE.match(stripped)
            or _ORDERED_RE.match(stripped)
            or _QUOTE_RE.match(stripped)
            or _DIVIDER_RE.match(stripped)
            or _FENCE_RE.match(stripped)):
            break

        out.append(stripped)
        i += 1

    return out, i


# ---------------------------------------------------------------------------
# Structure validation
# ---------------------------------------------------------------------------

# structure 항목 이름 → 파싱 결과 블록 클래스
_STRUCTURE_TO_BLOCK = {
    "heading":   HeadingBlock,
    "h1":        HeadingBlock,
    "h2":        HeadingBlock,
    "h3":        HeadingBlock,
    "h4":        HeadingBlock,
    "h5":        HeadingBlock,
    "h6":        HeadingBlock,
    "list":      ListBlock,
    "quote":     QuoteBlock,
    "divider":   DividerBlock,
    "paragraph": TextBlock,    # 파싱된 일반 텍스트는 TextBlock으로 매핑됨
    "text":      TextBlock,
}


def matches_structure(blocks: Iterable[Block], structure: Iterable[str]) -> bool:
    """파싱된 블록 시퀀스가 structure와 정확히 일치하는지 검사.

    strict 모드에서 사용. 길이도 같아야 하고 각 위치의 타입도 같아야 한다.
    """
    blocks_list = list(blocks)
    structure_list = list(structure)

    if len(blocks_list) != len(structure_list):
        return False

    for block, name in zip(blocks_list, structure_list):
        expected = _STRUCTURE_TO_BLOCK.get(name.lower())
        if expected is None:
            return False
        if not isinstance(block, expected):
            return False
    return True
