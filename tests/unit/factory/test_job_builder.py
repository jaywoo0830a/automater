"""
tests/unit/factory/test_job_builder.py
-----------------------------------
job_builder unit tests — Combination -> PostingSpec conversion rules.

DB-free: uses SimpleNamespace fakes for Combination, Campaign, Layout, Presets.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption, ParagraphBlock, HeadingBlock, ImageBlock,
    Section, TitleOption,
)
from factory.job_builder import (
    build_posting_spec,
    _build_body_default,
    _build_body_from_layout,
    _build_title,
    _build_values,
)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes
# ---------------------------------------------------------------------------

def _keyword(slug: str, value: str, cat_id: int = 1):
    category = SimpleNamespace(slug=slug, id=cat_id)
    return SimpleNamespace(category=category, value=value)


def _slot(sort_order: int, block_type: str, config: dict = None):
    return SimpleNamespace(
        sort_order=sort_order,
        block_type=block_type,
        config=config or {},
    )


def _layout(*slots):
    return SimpleNamespace(slots=list(slots))


def _preset(config: dict):
    return SimpleNamespace(config=config)


def _combo(
    keywords: list,
    title_template: str = "{region} {subject}",
    layout=None,
    publish_preset=None,
    run_preset=None,
):
    campaign = SimpleNamespace(
        title_template=title_template,
        layout=layout,
        publish_preset=publish_preset,
        run_preset=run_preset,
    )
    return SimpleNamespace(keywords=keywords, campaign=campaign)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


# ---------------------------------------------------------------------------
# _build_values
# ---------------------------------------------------------------------------

class TestBuildValues:

    def test_uses_keyword_value(self):
        combo = _combo(keywords=[
            _keyword("region", "강남구", cat_id=1),
            _keyword("subject", "수학", cat_id=2),
        ])
        values = _build_values(combo)
        assert values == {"region": "강남구", "subject": "수학"}

    def test_keywords_sorted_by_category_id(self):
        combo = _combo(keywords=[
            _keyword("subject", "수학", cat_id=2),
            _keyword("region", "강남구", cat_id=1),
        ])
        assert list(_build_values(combo).keys()) == ["region", "subject"]


# ---------------------------------------------------------------------------
# _build_title
# ---------------------------------------------------------------------------

class TestBuildTitle:

    def test_returns_title_option_with_template(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1), _keyword("subject", "수학", cat_id=2)],
            title_template="{region} {subject} {salt}",
        )
        opt = _build_title(combo)
        assert isinstance(opt, TitleOption)
        assert opt.template == "{region} {subject} {salt}"
        assert opt.values == {"region": "강남", "subject": "수학"}


# ---------------------------------------------------------------------------
# _build_body_default (fallback — no layout)
# ---------------------------------------------------------------------------

class TestBuildBodyDefault:

    def test_returns_three_paragraph_blocks(self):
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        sections = _build_body_default(combo)
        assert len(sections) == 1
        assert len(sections[0].blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in sections[0].blocks)

    def test_prompt_contains_keyword(self):
        combo = _combo(keywords=[
            _keyword("region", "강남", cat_id=1),
            _keyword("subject", "수학", cat_id=2),
        ])
        prompt = _build_body_default(combo)[0].blocks[0].prompt
        assert "강남" in prompt
        assert "수학" in prompt


# ---------------------------------------------------------------------------
# _build_body_from_layout (dynamic layout)
# ---------------------------------------------------------------------------

class TestBuildBodyFromLayout:

    def test_layout_with_paragraph_slots(self):
        layout = _layout(
            _slot(0, "paragraph", {"keyword": "{keyword}", "tone": "review"}),
            _slot(1, "paragraph", {"keyword": "{keyword}", "tone": "promotional"}),
        )
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            layout=layout,
        )
        sections = _build_body_from_layout(layout, combo)
        assert len(sections) == 1
        assert len(sections[0].blocks) == 2
        assert sections[0].blocks[0].keyword == "강남"
        assert sections[0].blocks[0].tone == "review"
        assert sections[0].blocks[1].tone == "promotional"

    def test_layout_with_mixed_blocks(self):
        layout = _layout(
            _slot(0, "heading", {"level": 2, "text": "{region} {subject} guide"}),
            _slot(1, "paragraph", {"keyword": "{keyword}"}),
            _slot(2, "image", {"path": "/img/{region}.jpg"}),
        )
        combo = _combo(keywords=[
            _keyword("region", "강남", cat_id=1),
            _keyword("subject", "수학", cat_id=2),
        ])
        sections = _build_body_from_layout(layout, combo)
        blocks = sections[0].blocks
        assert len(blocks) == 3
        assert isinstance(blocks[0], HeadingBlock)
        assert blocks[0].text == "강남 수학 guide"
        assert isinstance(blocks[1], ParagraphBlock)
        assert blocks[1].keyword == "강남 수학"
        assert isinstance(blocks[2], ImageBlock)
        assert blocks[2].path == "/img/강남.jpg"

    def test_empty_layout_falls_back_to_default(self):
        layout = _layout()
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        sections = _build_body_from_layout(layout, combo)
        assert len(sections[0].blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in sections[0].blocks)

    def test_slots_sorted_by_sort_order(self):
        layout = _layout(
            _slot(2, "paragraph", {"prompt": "second"}),
            _slot(0, "heading", {"level": 1, "text": "first"}),
        )
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        blocks = _build_body_from_layout(layout, combo)[0].blocks
        assert isinstance(blocks[0], HeadingBlock)
        assert isinstance(blocks[1], ParagraphBlock)

    def test_image_slot_with_media_id(self):
        """media_id in image slot is resolved to path via resolver."""
        resolver = lambda mid: f"/uploads/{mid}/photo.jpg"
        layout = _layout(
            _slot(0, "paragraph", {"keyword": "{keyword}"}),
            _slot(1, "image", {"media_id": 42}),
        )
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        blocks = _build_body_from_layout(layout, combo, media_resolver=resolver)[0].blocks
        assert len(blocks) == 2
        assert isinstance(blocks[1], ImageBlock)
        assert blocks[1].path == "/uploads/42/photo.jpg"

    def test_featured_slot_with_media_id_and_overlay(self):
        """Featured block resolves media_id and interpolates overlay."""
        resolver = lambda mid: f"/uploads/{mid}/thumb.jpg"
        layout = _layout(
            _slot(0, "featured", {"media_id": 7, "overlay_text": "{keyword}"}),
        )
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        blocks = _build_body_from_layout(layout, combo, media_resolver=resolver)[0].blocks
        from automator.options import FeaturedImageBlock
        assert isinstance(blocks[0], FeaturedImageBlock)
        assert blocks[0].path == "/uploads/7/thumb.jpg"
        assert blocks[0].overlay_text == "강남"

    def test_mixed_path_and_media_id(self):
        """Layout can mix explicit path and media_id slots."""
        resolver = lambda mid: f"/uploads/{mid}/img.jpg"
        layout = _layout(
            _slot(0, "image", {"path": "/explicit.jpg"}),
            _slot(1, "image", {"media_id": 10}),
        )
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        blocks = _build_body_from_layout(layout, combo, media_resolver=resolver)[0].blocks
        assert blocks[0].path == "/explicit.jpg"
        assert blocks[1].path == "/uploads/10/img.jpg"


# ---------------------------------------------------------------------------
# build_posting_spec — full composition
# ---------------------------------------------------------------------------

class TestBuildPostingSpec:

    def test_no_presets_uses_defaults(self):
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert isinstance(spec, PostingSpec)
        assert spec.publish.mode == "fixed"
        assert spec.publish.at == scheduled
        assert spec.setting.post_interval == 60  # RunSetting default

    def test_with_publish_preset(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            publish_preset=_preset({"mode": "random_window", "jitter_minutes": 45}),
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert spec.publish.mode == "random_window"
        assert spec.publish.jitter_minutes == 45
        assert spec.publish.at == scheduled  # always from dispatch

    def test_with_run_preset(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            run_preset=_preset({"post_interval": 120, "headless": False}),
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert spec.setting.post_interval == 120
        assert spec.setting.headless is False

    def test_with_layout(self):
        layout = _layout(
            _slot(0, "heading", {"level": 2, "text": "{keyword}"}),
            _slot(1, "paragraph", {"keyword": "{keyword}"}),
        )
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            layout=layout,
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert len(spec.body) == 1
        assert len(spec.body[0].blocks) == 2
        assert isinstance(spec.body[0].blocks[0], HeadingBlock)

    def test_all_three_presets(self):
        layout = _layout(_slot(0, "paragraph", {"keyword": "{keyword}"}))
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            layout=layout,
            publish_preset=_preset({"mode": "immediate"}),
            run_preset=_preset({"max_daily_posts": 3}),
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled)
        assert len(spec.body[0].blocks) == 1
        assert spec.publish.mode == "immediate"
        assert spec.setting.max_daily_posts == 3

    def test_naive_datetime_gets_kst(self):
        combo = _combo(keywords=[_keyword("region", "강남", cat_id=1)])
        naive = datetime(2099, 1, 1, 9, 0)
        spec = build_posting_spec(combo, _account(), naive)
        assert spec.publish.at.tzinfo is not None
        assert spec.publish.at.utcoffset() == timedelta(hours=9)

    def test_layout_with_media_id_and_resolver(self):
        """Full pipeline: layout with media_id resolves via media_resolver."""
        resolver = lambda mid: f"/uploads/{mid}/file.jpg"
        layout = _layout(
            _slot(0, "heading", {"level": 2, "text": "{keyword}"}),
            _slot(1, "image", {"media_id": 42}),
            _slot(2, "featured", {"media_id": 99, "overlay_text": "{keyword}"}),
        )
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            layout=layout,
        )
        scheduled = datetime.now(tz=KST) + timedelta(hours=2)
        spec = build_posting_spec(combo, _account(), scheduled, media_resolver=resolver)
        blocks = spec.body[0].blocks
        assert len(blocks) == 3
        assert blocks[1].path == "/uploads/42/file.jpg"
        assert blocks[2].path == "/uploads/99/file.jpg"
        assert blocks[2].overlay_text == "강남"
