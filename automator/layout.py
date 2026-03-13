"""
automator/layout.py
--------------------
ContentOption.layout 유효성 검사 및 alias 파싱 유틸리티.

Layout alias 규칙
-----------------
  "Image N"     — preview_images[N-1]  (N >= 1)
  "Thumbnail N" — thumbnail_images[N-1] (N >= 1)
  "Paragraph N" — N번째 단락 (N >= 1)

유효성 검사 규칙
----------------
  1. 각 alias는 위 세 패턴 중 하나여야 한다.
  2. "Image N"     — N <= len(preview_images)
  3. "Thumbnail N" — N <= len(thumbnail_images)
  4. "Paragraph N" — 1부터 연속 (gap 없음), 중복 없음
  5. 같은 alias가 두 번 이상 나오면 안 된다 (Image, Thumbnail 포함).
"""

from __future__ import annotations

import re
from automator.options import ContentOption

# ---------------------------------------------------------------------------
# Alias patterns
# ---------------------------------------------------------------------------

_IMAGE_RE     = re.compile(r"^Image (\d+)$")
_THUMBNAIL_RE = re.compile(r"^Thumbnail (\d+)$")
_PARAGRAPH_RE = re.compile(r"^Paragraph (\d+)$")


def parse_alias(alias: str) -> tuple[str, int]:
    """
    Parse an alias string into (kind, index).

    Returns:
        ("image",     N)  for "Image N"
        ("thumbnail", N)  for "Thumbnail N"
        ("paragraph", N)  for "Paragraph N"

    Raises:
        ValueError: If the alias does not match any known pattern.
    """
    for pattern, kind in (
        (_IMAGE_RE,     "image"),
        (_THUMBNAIL_RE, "thumbnail"),
        (_PARAGRAPH_RE, "paragraph"),
    ):
        m = pattern.match(alias)
        if m:
            return kind, int(m.group(1))
    raise ValueError(
        f"Unknown layout alias: {alias!r}. "
        "Expected 'Image N', 'Thumbnail N', or 'Paragraph N'."
    )


def paragraph_count(layout: list[str]) -> int:
    """
    Return the number of paragraphs implied by the layout.

    Counts the maximum N in all "Paragraph N" aliases.
    Returns 0 if no paragraph aliases are present.
    """
    counts = [
        int(m.group(1))
        for alias in layout
        if (m := _PARAGRAPH_RE.match(alias))
    ]
    return max(counts, default=0)


def validate_layout(option: ContentOption) -> None:
    """
    Raise ValueError if ContentOption.layout is invalid.

    Checks:
      - Each alias matches a known pattern.
      - "Image N"     → N <= len(preview_images), N >= 1
      - "Thumbnail N" → N <= len(thumbnail_images), N >= 1
      - "Paragraph N" → 1-based, contiguous, no duplicates
      - No duplicate aliases of any kind.
    """
    layout = option.layout
    if not layout:
        return  # empty layout is valid (no content)

    seen: set[str] = set()

    for alias in layout:
        # Duplicate check
        if alias in seen:
            raise ValueError(f"Duplicate alias in layout: {alias!r}")
        seen.add(alias)

        kind, n = parse_alias(alias)  # raises ValueError for unknown patterns

        if n < 1:
            raise ValueError(f"Alias index must be >= 1: {alias!r}")

        if kind == "image":
            if n > len(option.preview_images):
                raise ValueError(
                    f"{alias!r} referenced in layout but "
                    f"only {len(option.preview_images)} preview_image(s) provided."
                )

        elif kind == "thumbnail":
            if n > len(option.thumbnail_images):
                raise ValueError(
                    f"{alias!r} referenced in layout but "
                    f"only {len(option.thumbnail_images)} thumbnail_image(s) provided."
                )

    # Paragraph continuity check — must be 1, 2, 3, ... without gaps
    paragraph_ns = sorted(
        int(m.group(1))
        for alias in layout
        if (m := _PARAGRAPH_RE.match(alias))
    )
    if paragraph_ns and paragraph_ns != list(range(1, len(paragraph_ns) + 1)):
        raise ValueError(
            f"Paragraph aliases must be contiguous from 1. Got: "
            + ", ".join(f"Paragraph {n}" for n in paragraph_ns)
        )
