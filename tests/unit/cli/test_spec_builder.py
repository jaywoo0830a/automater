"""
tests/unit/cli/test_spec_builder.py
--------------------------------------
Combo + config → PostingSpec.

Covers:
    - Title construction
    - Post block parsing (paragraph = prompt string)
    - Image path resolution
    - Publish/run pass-through
"""

import pytest

from automator.contracts import PostingSpec
from automator.options import (
    HeadingBlock, ParagraphBlock, ImageBlock, FeaturedImageBlock,
    ListBlock, QuoteBlock, DividerBlock, Section,
)

from cli.combo_builder import Combo
from cli.spec_builder import build_spec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_CONFIG = {
    "accounts": [{"username": "u1", "password": "pw1", "blog_id": "b1"}],
    "titles": ["{pool:prefix} {keywords} 과외"],
    "keywords": {"region": ["강남"], "subject": ["수학"]},
    "pools": {"prefix": ["검증된"]},
    "post": [
        {"h2": "{keywords} 소개"},
        {"paragraph": "{keywords} 과외를 소개해줘"},
        {"image": "body.jpg"},
        {"paragraph": "{keywords} 과외 후기를 써줘. 200자 이상"},
        {"thumbnail": {"src": "thumb.jpg", "overlay": "{keywords} 과외"}},
    ],
    "images": "./images",
    "publish": {"schedule": "immediate", "tags": ["교육"]},
    "run": {"interval": "60s", "headless": True},
}


def _combo(**kw):
    defaults = {
        "values": {"region": "강남", "subject": "수학"},
        "title_template": "{keywords} 과외",
    }
    defaults.update(kw)
    return Combo(**defaults)


# ---------------------------------------------------------------------------
# PostingSpec basics
# ---------------------------------------------------------------------------

class TestBuildSpecBasics:

    def test_returns_posting_spec(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert isinstance(spec, PostingSpec)

    def test_account_mapped(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert spec.account.username == "u1"
        assert spec.account.password == "pw1"


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

class TestTitle:

    def test_template_from_combo(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert spec.title.template == "{keywords} 과외"

    def test_values_from_combo(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert spec.title.values == {"region": "강남", "subject": "수학"}

    def test_pools_from_config(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert spec.title.pools == {"prefix": ("검증된",)}


# ---------------------------------------------------------------------------
# Paragraph — always a prompt string
# ---------------------------------------------------------------------------

class TestParagraph:

    def test_simple_prompt(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{keywords} 과외를 소개해줘"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, ParagraphBlock)
        assert block.prompt == "강남 수학 과외를 소개해줘"

    def test_keywords_interpolated_in_prompt(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{keywords}가 4번 언급되는 글을 써줘. 3500자 이상"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.prompt == "강남 수학가 4번 언급되는 글을 써줘. 3500자 이상"

    def test_individual_keywords_in_prompt(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{keyword:region}에서 {keyword:subject} 과외를 찾고 계신가요?"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.prompt == "강남에서 수학 과외를 찾고 계신가요?"

    def test_pool_in_prompt(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{pool:prefix} {keywords} 과외를 소개해줘"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert "검증된" in block.prompt
        assert "강남 수학" in block.prompt

    def test_keyword_field_is_empty(self):
        """keyword field is never set — prompt goes straight to Gemini."""
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{keywords} 과외를 소개해줘"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.keyword == ""

    def test_pure_literal_prompt(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "자유 프롬프트 — DSL 토큰 없이도 동작한다"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.prompt == "자유 프롬프트 — DSL 토큰 없이도 동작한다"


# ---------------------------------------------------------------------------
# Other blocks — shorthand
# ---------------------------------------------------------------------------

class TestPostShorthand:

    def test_heading_from_string(self):
        config = {**FULL_CONFIG, "post": [{"h2": "{keywords} 소개"}]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, HeadingBlock)
        assert block.level == 2
        assert block.text == "강남 수학 소개"

    def test_h3_heading(self):
        config = {**FULL_CONFIG, "post": [{"h3": "방문 팁"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].level == 3

    def test_image_from_string(self):
        config = {**FULL_CONFIG, "post": [{"image": "photo.jpg"}]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, ImageBlock)
        assert block.path == "images/photo.jpg"

    def test_thumbnail_from_string(self):
        config = {**FULL_CONFIG, "post": [{"thumbnail": "thumb.jpg"}]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, FeaturedImageBlock)
        assert block.path == "images/thumb.jpg"

    def test_quote_from_string(self):
        config = {**FULL_CONFIG, "post": [{"quote": "인용문"}]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, QuoteBlock)
        assert block.text == "인용문"

    def test_divider(self):
        config = {**FULL_CONFIG, "post": ["divider"]}
        spec = build_spec(_combo(), config)
        assert isinstance(spec.body[0].blocks[0], DividerBlock)


# ---------------------------------------------------------------------------
# Other blocks — full dict
# ---------------------------------------------------------------------------

class TestPostFullDict:

    def test_image_with_options(self):
        config = {**FULL_CONFIG, "post": [
            {"image": {"src": "photo.jpg", "alt": "{keywords} 외관"}},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.path == "images/photo.jpg"
        assert block.alt == "강남 수학 외관"

    def test_thumbnail_with_options(self):
        config = {**FULL_CONFIG, "post": [
            {"thumbnail": {"src": "thumb.jpg", "overlay": "{keywords} 과외"}},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.overlay_text == "강남 수학 과외"

    def test_quote_with_attribution(self):
        config = {**FULL_CONFIG, "post": [
            {"quote": {"text": "인용", "by": "작가"}},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert block.text == "인용"
        assert block.attribution == "작가"


# ---------------------------------------------------------------------------
# List block
# ---------------------------------------------------------------------------

class TestListBlock:

    def test_list_from_items(self):
        config = {**FULL_CONFIG, "post": [
            {"list": ["항목 1", "항목 2", "항목 3"]},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, ListBlock)
        assert block.items == ("항목 1", "항목 2", "항목 3")


# ---------------------------------------------------------------------------
# Full layout order
# ---------------------------------------------------------------------------

class TestFullLayout:

    def test_blocks_in_order(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        blocks = spec.body[0].blocks
        assert len(blocks) == 5
        assert isinstance(blocks[0], HeadingBlock)
        assert isinstance(blocks[1], ParagraphBlock)
        assert isinstance(blocks[2], ImageBlock)
        assert isinstance(blocks[3], ParagraphBlock)
        assert isinstance(blocks[4], FeaturedImageBlock)


# ---------------------------------------------------------------------------
# Image base dir
# ---------------------------------------------------------------------------

class TestImageBaseDir:

    def test_images_dir_prepended(self):
        config = {**FULL_CONFIG, "images": "./photos", "post": [{"image": "a.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "photos/a.jpg"

    def test_no_images_dir(self):
        config = {**FULL_CONFIG, "post": [{"image": "a.jpg"}]}
        del config["images"]
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "a.jpg"


# ---------------------------------------------------------------------------
# Default body
# ---------------------------------------------------------------------------

class TestDefaultBody:

    def test_no_post_generates_default(self):
        config = {**FULL_CONFIG}
        del config["post"]
        spec = build_spec(_combo(), config)
        blocks = spec.body[0].blocks
        assert len(blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in blocks)
