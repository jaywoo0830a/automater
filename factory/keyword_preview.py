"""
factory/keyword_preview.py
-----------------------------
Pure-function keyword import preview — no DB, no side effects.

Sits between Excel parsing (excel_parser.parse_rows) and
DB persistence (BulkImporter.import_keywords).

SPA workflow:
    1. Upload Excel  → excel_parser.parse_rows → raw data
    2. Preview       → preview_keywords(raw_data) → KeywordPreviewResult
    3. User reviews the preview and confirms
    4. Confirm       → BulkImporter.import_keywords(raw_data)
"""

from __future__ import annotations

from dataclasses import dataclass
from math import prod


_MAX_SAMPLE_VALUES = 5


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryPreview:
    """Preview of one keyword category."""
    slug:            str
    keyword_count:   int
    sample_values:   list[str]


@dataclass(frozen=True)
class KeywordPreviewResult:
    """Preview of an entire keyword import operation."""
    categories:              list[CategoryPreview]
    total_keywords:          int
    estimated_combinations:  int
    title_template:          str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preview_keywords(data: dict[str, list[str]]) -> KeywordPreviewResult:
    """
    Preview what a keyword import would produce — no DB access.

    Args:
        data: {category_slug: [keyword_values]} from parse_rows
              or resolve_headers.

    Returns:
        KeywordPreviewResult with category breakdowns,
        total keyword count, estimated combinations,
        and auto-generated title template.

    Raises:
        ValueError: If data is empty.
    """
    if not data:
        raise ValueError("data must not be empty")

    categories: list[CategoryPreview] = []
    counts: list[int] = []

    for slug, raw_values in data.items():
        clean = _deduplicate_and_clean(raw_values)
        categories.append(CategoryPreview(
            slug=slug,
            keyword_count=len(clean),
            sample_values=clean[:_MAX_SAMPLE_VALUES],
        ))
        counts.append(len(clean))

    total_keywords = sum(c.keyword_count for c in categories)
    estimated_combinations = prod(counts) if counts else 0
    title_template = _build_title_template([c.slug for c in categories])

    return KeywordPreviewResult(
        categories=categories,
        total_keywords=total_keywords,
        estimated_combinations=estimated_combinations,
        title_template=title_template,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deduplicate_and_clean(values: list[str]) -> list[str]:
    """Strip whitespace, remove empties, deduplicate (order-preserved)."""
    seen: set[str] = set()
    result: list[str] = []
    for v in values:
        stripped = v.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        result.append(stripped)
    return result


def _build_title_template(slugs: list[str]) -> str:
    """Build a title template string from category slugs in order."""
    return " ".join(f"{{{s}}}" for s in slugs)
