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
    _apply_affixes,
    _build_body_default,
    _build_body_from_layout,
    _build_override_lookup,
    _build_pools,
    _build_template,
    _build_title,
    _build_values,
)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes
# ---------------------------------------------------------------------------

def _keyword(slug: str, value: str, cat_id: int = 1, affixes=None, kw_id: int = 0):
    category = SimpleNamespace(slug=slug, id=cat_id)
    return SimpleNamespace(
        id=kw_id, category=category, value=value, affixes=affixes or [],
    )


def _affix(type: str, value: str, affix_id: int = 0):
    return SimpleNamespace(id=affix_id, type=type, value=value)


def _override(affix_id: int, keyword_id: int, active: bool):
    return SimpleNamespace(affix_id=affix_id, keyword_id=keyword_id, active=active)


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


def _palette_item(value: str, active: bool = True):
    return SimpleNamespace(value=value, active=active)


def _palette(strategy: str = "random", items: list = None):
    return SimpleNamespace(strategy=strategy, items=items or [])


def _token(slug: str, token_type: str = "keyword", palette=None, value=None, sort_order: int = 0):
    return SimpleNamespace(
        slug=slug, token_type=token_type,
        palette=palette, value=value, sort_order=sort_order,
    )


def _combo(
    keywords: list,
    layout=None,
    publish_preset=None,
    run_preset=None,
    affix_overrides=None,
    tokens=None,
):
    campaign = SimpleNamespace(
        layout=layout,
        publish_preset=publish_preset,
        run_preset=run_preset,
        affix_overrides=affix_overrides or [],
        tokens=tokens or [],
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
            _keyword("region", "강남", cat_id=1),
        ])
        values = _build_values(combo)
        assert list(values.keys()) == ["region", "subject"]

    # -- affix stripping (campaign override controls active/inactive) --

    def test_override_inactive_suffix_stripped(self):
        """강남구 + suffix "구" overridden active=False → 강남"""
        kw = _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[_override(affix_id=1, keyword_id=10, active=False)],
        )
        values = _build_values(combo)
        assert values["region"] == "강남"

    def test_override_active_suffix_kept(self):
        """강남구 + suffix "구" overridden active=True → 강남구"""
        kw = _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[_override(affix_id=1, keyword_id=10, active=True)],
        )
        values = _build_values(combo)
        assert values["region"] == "강남구"

    def test_no_override_keeps_affix(self):
        """No override → affix is kept (default = active)."""
        kw = _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
        ])
        combo = _combo(keywords=[kw], affix_overrides=[])
        values = _build_values(combo)
        assert values["region"] == "강남구"

    def test_override_inactive_prefix_stripped(self):
        """동강남 + prefix "동" overridden active=False → 강남"""
        kw = _keyword("region", "동강남", cat_id=1, kw_id=10, affixes=[
            _affix("prefix", "동", affix_id=2),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[_override(affix_id=2, keyword_id=10, active=False)],
        )
        values = _build_values(combo)
        assert values["region"] == "강남"

    def test_override_active_prefix_kept(self):
        """동강남 + prefix "동" overridden active=True → 동강남"""
        kw = _keyword("region", "동강남", cat_id=1, kw_id=10, affixes=[
            _affix("prefix", "동", affix_id=2),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[_override(affix_id=2, keyword_id=10, active=True)],
        )
        values = _build_values(combo)
        assert values["region"] == "동강남"

    def test_multiple_overrides_inactive(self):
        """서초구 + two suffixes both overridden inactive → 서초"""
        kw = _keyword("region", "서초구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
            _affix("suffix", "동", affix_id=2),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[
                _override(affix_id=1, keyword_id=10, active=False),
                _override(affix_id=2, keyword_id=10, active=False),
            ],
        )
        values = _build_values(combo)
        assert values["region"] == "서초"

    def test_mixed_overrides(self):
        """강남구 + suffix "구" inactive, suffix "동" active → 강남"""
        kw = _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
            _affix("suffix", "동", affix_id=2),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[
                _override(affix_id=1, keyword_id=10, active=False),
                _override(affix_id=2, keyword_id=10, active=True),
            ],
        )
        values = _build_values(combo)
        assert values["region"] == "강남"

    def test_no_affixes_unchanged(self):
        """No affixes → value unchanged."""
        combo = _combo(keywords=[
            _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[]),
        ])
        values = _build_values(combo)
        assert values["region"] == "강남구"

    def test_suffix_not_in_value_unchanged(self):
        """Suffix doesn't match end of value → unchanged."""
        kw = _keyword("region", "강남", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
        ])
        combo = _combo(
            keywords=[kw],
            affix_overrides=[_override(affix_id=1, keyword_id=10, active=False)],
        )
        values = _build_values(combo)
        assert values["region"] == "강남"

    def test_two_keywords_independent_overrides(self):
        """Each keyword's override is independent."""
        kw1 = _keyword("region", "강남구", cat_id=1, kw_id=10, affixes=[
            _affix("suffix", "구", affix_id=1),
        ])
        kw2 = _keyword("subject", "수학", cat_id=2, kw_id=20, affixes=[])
        combo = _combo(
            keywords=[kw1, kw2],
            affix_overrides=[_override(affix_id=1, keyword_id=10, active=False)],
        )
        values = _build_values(combo)
        assert values == {"region": "강남", "subject": "수학"}

    def test_same_affix_different_keyword_overrides(self):
        """Same affix "동" stripped from 수리동 but kept for 산본동."""
        dong = _affix("suffix", "동", affix_id=1)
        kw1 = _keyword("region", "수리동", cat_id=1, kw_id=10, affixes=[dong])
        kw2 = _keyword("region2", "산본동", cat_id=3, kw_id=20, affixes=[dong])
        combo = _combo(
            keywords=[kw1, kw2],
            affix_overrides=[
                _override(affix_id=1, keyword_id=10, active=False),
                _override(affix_id=1, keyword_id=20, active=True),
            ],
        )
        values = _build_values(combo)
        assert values["region"] == "수리"
        assert values["region2"] == "산본동"


# ---------------------------------------------------------------------------
# _build_title
# ---------------------------------------------------------------------------

class TestBuildTemplate:

    def test_keyword_tokens_produce_slug_placeholders(self):
        campaign = SimpleNamespace(tokens=[
            _token("region", "keyword", sort_order=0),
            _token("subject", "keyword", sort_order=1),
        ])
        assert _build_template(campaign) == "{region} {subject}"

    def test_pool_tokens_produce_slug_placeholders(self):
        campaign = SimpleNamespace(tokens=[
            _token("region", "keyword", sort_order=0),
            _token("salt_suffix", "pool", sort_order=1),
        ])
        assert _build_template(campaign) == "{region} {salt_suffix}"

    def test_literal_token_produces_raw_value(self):
        campaign = SimpleNamespace(tokens=[
            _token("region", "keyword", sort_order=0),
            _token("_lit_expert", "literal", value="전문", sort_order=1),
            _token("subject", "keyword", sort_order=2),
        ])
        assert _build_template(campaign) == "{region} 전문 {subject}"

    def test_sort_order_respected(self):
        campaign = SimpleNamespace(tokens=[
            _token("subject", "keyword", sort_order=2),
            _token("salt_prefix", "pool", sort_order=0),
            _token("region", "keyword", sort_order=1),
        ])
        assert _build_template(campaign) == "{salt_prefix} {region} {subject}"

    def test_empty_tokens(self):
        campaign = SimpleNamespace(tokens=[])
        assert _build_template(campaign) == ""

    def test_no_tokens_attribute(self):
        campaign = SimpleNamespace()
        assert _build_template(campaign) == ""

    def test_mixed_all_types(self):
        campaign = SimpleNamespace(tokens=[
            _token("salt_prefix", "pool", sort_order=0),
            _token("region", "keyword", sort_order=1),
            _token("_lit_best", "literal", value="최고의", sort_order=2),
            _token("subject", "keyword", sort_order=3),
            _token("cta", "pool", sort_order=4),
        ])
        assert _build_template(campaign) == "{salt_prefix} {region} 최고의 {subject} {cta}"


# ---------------------------------------------------------------------------
# _build_title
# ---------------------------------------------------------------------------

class TestBuildTitle:

    def test_returns_title_option_with_template_from_tokens(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1), _keyword("subject", "수학", cat_id=2)],
            tokens=[
                _token("region", "keyword", sort_order=0),
                _token("subject", "keyword", sort_order=1),
                _token("salt_suffix", "pool", sort_order=2),
            ],
        )
        opt = _build_title(combo)
        assert isinstance(opt, TitleOption)
        assert opt.template == "{region} {subject} {salt_suffix}"
        assert opt.values == {"region": "강남", "subject": "수학"}

    def test_pools_loaded_from_tokens(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            tokens=[
                _token("region", "keyword", sort_order=0),
                _token("salt_suffix", "pool", sort_order=1, palette=_palette(items=[
                    _palette_item("강력 추천"),
                    _palette_item("즉시 가능"),
                ])),
            ],
        )
        opt = _build_title(combo)
        assert opt.pools == {"salt_suffix": ("강력 추천", "즉시 가능")}

    def test_multiple_pool_tokens(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            tokens=[
                _token("salt_prefix", "pool", sort_order=0, palette=_palette(items=[
                    _palette_item("검증된"), _palette_item("전문"),
                ])),
                _token("region", "keyword", sort_order=1),
                _token("cta", "pool", sort_order=2, palette=_palette(items=[
                    _palette_item("지금 신청"),
                ])),
            ],
        )
        opt = _build_title(combo)
        assert opt.template == "{salt_prefix} {region} {cta}"
        assert opt.pools["salt_prefix"] == ("검증된", "전문")
        assert opt.pools["cta"] == ("지금 신청",)

    def test_inactive_palette_items_excluded(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            tokens=[
                _token("region", "keyword", sort_order=0),
                _token("salt_suffix", "pool", sort_order=1, palette=_palette(items=[
                    _palette_item("강력 추천", active=True),
                    _palette_item("삭제됨", active=False),
                ])),
            ],
        )
        opt = _build_title(combo)
        assert opt.pools == {"salt_suffix": ("강력 추천",)}

    def test_literal_token_in_template(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
            tokens=[
                _token("region", "keyword", sort_order=0),
                _token("_lit_expert", "literal", value="전문", sort_order=1),
                _token("subject", "keyword", sort_order=2),
            ],
        )
        opt = _build_title(combo)
        assert opt.template == "{region} 전문 {subject}"

    def test_no_tokens_empty_template(self):
        combo = _combo(
            keywords=[_keyword("region", "강남", cat_id=1)],
        )
        opt = _build_title(combo)
        assert opt.template == ""
        assert opt.pools == {}


# ---------------------------------------------------------------------------
# _build_pools
# ---------------------------------------------------------------------------

class TestBuildPools:

    def test_builds_pools_from_tokens(self):
        campaign = SimpleNamespace(tokens=[
            _token("salt_prefix", "pool", palette=_palette(items=[
                _palette_item("검증된"), _palette_item("전문"),
            ])),
            _token("salt_suffix", "pool", palette=_palette(items=[
                _palette_item("강력 추천"),
            ])),
        ])
        pools = _build_pools(campaign)
        assert pools == {
            "salt_prefix": ("검증된", "전문"),
            "salt_suffix": ("강력 추천",),
        }

    def test_filters_inactive_items(self):
        campaign = SimpleNamespace(tokens=[
            _token("cta", "pool", palette=_palette(items=[
                _palette_item("지금 신청", active=True),
                _palette_item("삭제됨", active=False),
                _palette_item("무료 상담", active=True),
            ])),
        ])
        pools = _build_pools(campaign)
        assert pools == {"cta": ("지금 신청", "무료 상담")}

    def test_keyword_tokens_excluded(self):
        campaign = SimpleNamespace(tokens=[
            _token("region", "keyword"),
            _token("salt_suffix", "pool", palette=_palette(items=[
                _palette_item("추천"),
            ])),
        ])
        pools = _build_pools(campaign)
        assert "region" not in pools
        assert pools == {"salt_suffix": ("추천",)}

    def test_empty_tokens(self):
        pools = _build_pools(SimpleNamespace(tokens=[]))
        assert pools == {}

    def test_no_tokens_attribute(self):
        pools = _build_pools(SimpleNamespace())
        assert pools == {}


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
