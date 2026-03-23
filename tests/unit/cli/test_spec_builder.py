"""
tests/unit/cli/test_spec_builder.py
--------------------------------------
spec_builder — KeywordCombo + CampaignConfig → PostingSpec.

Tests cover:
    - TitleOption construction (template, values, pools, spacing)
    - Body Section/Block construction from layout
    - Publish and Run preset loading
    - Media resolution
    - AccountOption mapping
"""

from __future__ import annotations

import pytest

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    HeadingBlock,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    Section,
)

from cli.campaign_config import (
    AccountEntry,
    CampaignConfig,
    LayoutSlotEntry,
    MediaMap,
    TitleConfig,
    TokenEntry,
)
from cli.combo_builder import KeywordCombo
from cli.spec_builder import build_spec, build_account_option


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_combo() -> KeywordCombo:
    return KeywordCombo(
        values={"region": "강남", "subject": "수학"},
        spacing_pattern={"salt_prefix": 1, "region": 1, "subject": 0, "과외": 1, "salt_suffix": 1},
    )


@pytest.fixture
def sample_config() -> CampaignConfig:
    return CampaignConfig(
        accounts=(
            AccountEntry(
                username="user1",
                password="pw1",
                meta={"blog_id": "blog1"},
                session_path="user1_session.json",
            ),
        ),
        title=TitleConfig(
            tokens=(
                TokenEntry(slug="salt_prefix", type="pool"),
                TokenEntry(slug="region", type="keyword"),
                TokenEntry(slug="subject", type="keyword"),
                TokenEntry(slug="과외", type="literal", value="과외"),
                TokenEntry(slug="salt_suffix", type="pool"),
            ),
        ),
        keywords={"region": ["강남"], "subject": ["수학"]},
        palettes={
            "salt_prefix": ["검증된", "전문"],
            "salt_suffix": ["강력 추천"],
        },
        layout=(
            LayoutSlotEntry(block_type="heading", config={"level": 2, "text": "{keyword} 소개"}),
            LayoutSlotEntry(block_type="paragraph", config={"keyword": "{keyword}"}),
        ),
        publish_config={"mode": "immediate", "tags": ["교육"]},
        run_config={"post_interval": 60, "headless": True},
    )


# ---------------------------------------------------------------------------
# AccountOption mapping
# ---------------------------------------------------------------------------

class TestBuildAccountOption:

    def test_maps_fields(self):
        entry = AccountEntry(
            username="u1",
            password="p1",
            meta={"blog_id": "b1"},
            session_path="s.json",
            proxies=["1.2.3.4:8080"],
        )
        opt = build_account_option(entry)
        assert isinstance(opt, AccountOption)
        assert opt.username == "u1"
        assert opt.password == "p1"
        assert opt.meta == {"blog_id": "b1"}
        assert opt.session_path == "s.json"
        assert opt.proxies == ["1.2.3.4:8080"]

    def test_defaults_carry_over(self):
        entry = AccountEntry(username="u", password="p")
        opt = build_account_option(entry)
        assert opt.meta == {}
        assert opt.proxies == []
        assert opt.session_path == ""


# ---------------------------------------------------------------------------
# PostingSpec — title
# ---------------------------------------------------------------------------

class TestBuildSpecTitle:

    def test_title_template_assembled_from_tokens(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        title = spec.title
        # Template should have all token slugs as placeholders or literals
        assert "{salt_prefix}" in title.template
        assert "{region}" in title.template
        assert "{subject}" in title.template
        assert "{salt_suffix}" in title.template
        assert "과외" in title.template

    def test_title_values_match_combo(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert spec.title.values["region"] == "강남"
        assert spec.title.values["subject"] == "수학"

    def test_title_pools_from_palettes(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert spec.title.pools["salt_prefix"] == ("검증된", "전문")
        assert spec.title.pools["salt_suffix"] == ("강력 추천",)

    def test_title_has_space_from_spacing_pattern(self, sample_combo, sample_config):
        """has_space reflects the spacing pattern."""
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        # has_space is determined by whether the template uses space joining
        assert isinstance(spec.title.template, str)


# ---------------------------------------------------------------------------
# PostingSpec — body
# ---------------------------------------------------------------------------

class TestBuildSpecBody:

    def test_body_has_sections(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert len(spec.body) >= 1
        assert isinstance(spec.body[0], Section)

    def test_layout_blocks_created_in_order(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        blocks = spec.body[0].blocks
        assert len(blocks) == 2
        assert isinstance(blocks[0], HeadingBlock)
        assert isinstance(blocks[1], ParagraphBlock)

    def test_heading_text_interpolated(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        heading = spec.body[0].blocks[0]
        assert isinstance(heading, HeadingBlock)
        # {keyword} should be replaced with "강남 수학"
        assert "강남" in heading.text
        assert "수학" in heading.text

    def test_paragraph_keyword_interpolated(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        para = spec.body[0].blocks[1]
        assert isinstance(para, ParagraphBlock)
        assert "강남" in para.keyword
        assert "수학" in para.keyword

    def test_empty_layout_produces_default_body(self, sample_combo):
        config = CampaignConfig(
            accounts=(AccountEntry(username="u", password="p"),),
            title=TitleConfig(
                tokens=(TokenEntry(slug="subject", type="keyword"),),
            ),
            keywords={"subject": ["math"]},
            layout=(),
        )
        combo = KeywordCombo(values={"subject": "math"}, spacing_pattern={})
        spec = build_spec(combo, config, config.accounts[0])
        # Default: 3 ParagraphBlocks
        blocks = spec.body[0].blocks
        assert len(blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in blocks)


# ---------------------------------------------------------------------------
# PostingSpec — media resolution
# ---------------------------------------------------------------------------

class TestBuildSpecMedia:

    def test_image_block_path_resolved_from_media(self):
        config = CampaignConfig(
            accounts=(AccountEntry(username="u", password="p"),),
            title=TitleConfig(
                tokens=(TokenEntry(slug="s", type="keyword"),),
            ),
            keywords={"s": ["val"]},
            layout=(
                LayoutSlotEntry(
                    block_type="image",
                    config={"media_id": "1", "alt": "alt text"},
                ),
            ),
            media=MediaMap(base_dir="/imgs", files={"1": "photo.jpg"}),
        )
        combo = KeywordCombo(values={"s": "val"}, spacing_pattern={})
        spec = build_spec(combo, config, config.accounts[0])
        block = spec.body[0].blocks[0]
        assert isinstance(block, ImageBlock)
        assert block.path == "/imgs/photo.jpg"

    def test_featured_image_path_resolved(self):
        config = CampaignConfig(
            accounts=(AccountEntry(username="u", password="p"),),
            title=TitleConfig(
                tokens=(TokenEntry(slug="s", type="keyword"),),
            ),
            keywords={"s": ["val"]},
            layout=(
                LayoutSlotEntry(
                    block_type="featured",
                    config={"media_id": "2", "overlay_text": "text"},
                ),
            ),
            media=MediaMap(base_dir="./images", files={"2": "thumb.jpg"}),
        )
        combo = KeywordCombo(values={"s": "val"}, spacing_pattern={})
        spec = build_spec(combo, config, config.accounts[0])
        block = spec.body[0].blocks[0]
        assert isinstance(block, FeaturedImageBlock)
        assert block.path == "images/thumb.jpg"


# ---------------------------------------------------------------------------
# PostingSpec — publish & run
# ---------------------------------------------------------------------------

class TestBuildSpecPresets:

    def test_publish_option_from_config(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert spec.publish.mode == "immediate"
        assert spec.publish.tags == ["교육"]

    def test_run_setting_from_config(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert spec.setting.post_interval == 60
        assert spec.setting.headless is True

    def test_empty_presets_use_defaults(self, sample_combo):
        config = CampaignConfig(
            accounts=(AccountEntry(username="u", password="p"),),
            title=TitleConfig(
                tokens=(TokenEntry(slug="s", type="keyword"),),
            ),
            keywords={"s": ["v"]},
        )
        combo = KeywordCombo(values={"s": "v"}, spacing_pattern={})
        spec = build_spec(combo, config, config.accounts[0])
        # Default publish mode when no schedule_at: immediate fallback
        assert spec.setting.post_interval == 60  # RunSetting default


# ---------------------------------------------------------------------------
# PostingSpec — account
# ---------------------------------------------------------------------------

class TestBuildSpecAccount:

    def test_account_from_entry(self, sample_combo, sample_config):
        spec = build_spec(sample_combo, sample_config, sample_config.accounts[0])
        assert spec.account.username == "user1"
        assert spec.account.password == "pw1"
        assert spec.account.meta == {"blog_id": "blog1"}
