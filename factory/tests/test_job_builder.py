"""
factory/tests/test_job_builder.py
-----------------------------------
job_builder unit tests — Combination -> PostingSpec conversion rules.

DB-free: uses Mock objects.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from automator.contracts import PostingSpec
from automator.options import AccountOption, ParagraphBlock, Section, TitleOption
from factory.job_builder import (
    build_posting_spec,
    _build_body,
    _build_title_option,
    _build_values,
)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers — lightweight Combination / Keyword / Campaign fakes
# ---------------------------------------------------------------------------

def _keyword(slug: str, value: str, cat_id: int = 1):
    """Fake Keyword with .category.slug, .value."""
    category = SimpleNamespace(slug=slug, id=cat_id)
    return SimpleNamespace(
        category=category,
        value=value,
    )


def _combo(
    keywords: list,
    title_template: str = "{region} {subject}",
):
    """Fake Combination with .keywords, .campaign, .config."""
    campaign = SimpleNamespace(title_template=title_template)
    return SimpleNamespace(
        keywords=keywords,
        campaign=campaign,
        config={},
    )


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


# ---------------------------------------------------------------------------
# _build_values
# ---------------------------------------------------------------------------

class TestBuildValues:

    def test_uses_keyword_value(self):
        combo = _combo(
            keywords=[
                _keyword("region", "강남구", cat_id=1),
                _keyword("subject", "수학", cat_id=2),
            ],
        )
        values = _build_values(combo)
        assert values["region"] == "강남구"
        assert values["subject"] == "수학"

    def test_keywords_sorted_by_category_id(self):
        combo = _combo(
            keywords=[
                _keyword("subject", "수학", cat_id=2),
                _keyword("region", "강남구", cat_id=1),
            ],
        )
        values = _build_values(combo)
        assert list(values.keys()) == ["region", "subject"]


# ---------------------------------------------------------------------------
# _build_title_option
# ---------------------------------------------------------------------------

class TestBuildTitleOption:

    def test_returns_title_option_with_template(self):
        combo = _combo(
            keywords=[
                _keyword("region", "강남", cat_id=1),
                _keyword("subject", "수학", cat_id=2),
            ],
            title_template="{region} {subject} {salt}",
        )
        opt = _build_title_option(combo)
        assert isinstance(opt, TitleOption)
        assert opt.template == "{region} {subject} {salt}"
        assert opt.values["region"] == "강남"
        assert opt.values["subject"] == "수학"


# ---------------------------------------------------------------------------
# _build_body
# ---------------------------------------------------------------------------

class TestBuildBody:

    def test_returns_single_section_with_three_paragraph_blocks(self):
        combo = _combo(
            keywords=[
                _keyword("region", "강남", cat_id=1),
                _keyword("subject", "수학", cat_id=2),
            ],
        )
        sections = _build_body(combo)
        assert len(sections) == 1
        assert isinstance(sections[0], Section)
        assert len(sections[0].blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in sections[0].blocks)

    def test_prompt_contains_keyword(self):
        combo = _combo(
            keywords=[
                _keyword("region", "강남", cat_id=1),
                _keyword("subject", "수학", cat_id=2),
            ],
        )
        sections = _build_body(combo)
        prompt = sections[0].blocks[0].prompt
        assert "강남" in prompt
        assert "수학" in prompt


# ---------------------------------------------------------------------------
# build_posting_job
# ---------------------------------------------------------------------------

class TestBuildPostingSpec:

    def test_returns_posting_spec(self):
        combo = _combo(
            keywords=[
                _keyword("region", "강남", cat_id=1),
                _keyword("subject", "수학", cat_id=2),
            ],
            title_template="{region} {subject}",
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert isinstance(spec, PostingSpec)
        assert spec.account is not None
        assert spec.title is not None
        assert len(spec.body) == 1
        assert spec.publish is not None
        assert spec.publish.mode == "fixed"
        assert spec.publish.at == scheduled

    def test_naive_datetime_gets_kst_attached(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            title_template="{region}",
        )
        naive = datetime(2099, 1, 1, 9, 0)
        spec = build_posting_spec(combo, _account(), naive)
        assert spec.publish.at.tzinfo is not None
        assert spec.publish.at.utcoffset() == timedelta(hours=9)

    def test_aware_datetime_preserved(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            title_template="{region}",
        )
        aware = datetime(2099, 1, 1, 9, 0, tzinfo=KST)
        spec = build_posting_spec(combo, _account(), aware)
        assert spec.publish.at is aware
