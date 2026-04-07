"""
tests/unit/cli/test_spec_builder.py
--------------------------------------
Combo + config → PostingSpec.

Covers: title, paragraph prompt, image path interpolation,
        {i} counter, when conditions, account override.
"""

import pytest

from automator.contracts import PostingSpec
from automator.options import (
    HeadingBlock, ParagraphBlock, ImageBlock, FeaturedImageBlock,
    ListBlock, QuoteBlock, DividerBlock, Section, TitleOption,
)

from cli.combo_builder import Combo
from cli.spec_builder import build_spec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_CONFIG = {
    "accounts": [{"username": "u1", "password": "pw1", "blog_id": "b1"}],
    "titles": ["{pool:prefix} {keyword:region} {keyword:subject} 과외"],
    "keywords": {"region": ["강남"], "subject": ["수학"]},
    "pools": {"prefix": ["검증된"]},
    "post": [
        {"h2": "{keyword:region} {keyword:subject} 과외 소개"},
        {"paragraph": "{keyword:region} {keyword:subject} 과외를 소개해줘"},
        {"image": "body.jpg"},
        {"paragraph": "{keyword:region} {keyword:subject} 과외 후기를 써줘"},
        {"featured_image": {"path": "thumb.jpg", "overlay_text": "{keyword:region} {keyword:subject} 과외"}},
    ],
    "assets": "./images",
    "publish": {"schedule": "immediate", "tags": ["교육"]},
    "run": {"interval": "60s", "headless": True},
}


def _combo(**kw):
    defaults = {
        "values": {"region": "강남", "subject": "수학"},
        "title_template": "{keyword:region} {keyword:subject} 과외",
        "index": 1,
    }
    defaults.update(kw)
    return Combo(**defaults)


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------

class TestBasics:

    def test_returns_posting_spec(self):
        assert isinstance(build_spec(_combo(), FULL_CONFIG), PostingSpec)

    def test_account_mapped(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        assert spec.account.username == "u1"


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

class TestTitle:

    def test_template(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        title = spec.title
        assert isinstance(title, TitleOption)
        assert title.template == "{keyword:region} {keyword:subject} 과외"

    def test_values(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        title = spec.title
        assert isinstance(title, TitleOption)
        assert title.values == {"region": "강남", "subject": "수학"}

    def test_pools(self):
        spec = build_spec(_combo(), FULL_CONFIG)
        title = spec.title
        assert isinstance(title, TitleOption)
        assert title.pools == {"prefix": ("검증된",)}

    def test_i_in_title(self):
        config = {**FULL_CONFIG, "titles": ["#{i} {keyword:region}"]}
        spec = build_spec(_combo(title_template="#{i} {keyword:region}", index=7), config)
        title = spec.title
        assert isinstance(title, TitleOption)
        assert "7" in title.template
        assert "{i}" not in title.template


# ---------------------------------------------------------------------------
# Paragraph — prompt string
# ---------------------------------------------------------------------------

class TestParagraph:

    def test_simple(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "{keyword:region} {keyword:subject} 과외를 소개해줘"},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert isinstance(block, ParagraphBlock)
        assert block.prompt == "강남 수학 과외를 소개해줘"

    def test_prompt_interpolated(self):
        config = {**FULL_CONFIG, "post": [{"paragraph": "{keyword:region} 소개"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].prompt == "강남 소개"

    def test_i_in_prompt(self):
        config = {**FULL_CONFIG, "post": [{"paragraph": "포스팅 #{i}"}]}
        spec = build_spec(_combo(index=3), config)
        assert spec.body[0].blocks[0].prompt == "포스팅 #3"


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------

class TestHeading:

    def test_h2(self):
        config = {**FULL_CONFIG, "post": [{"h2": "{keyword:region} 소개"}]}
        spec = build_spec(_combo(), config)
        b = spec.body[0].blocks[0]
        assert isinstance(b, HeadingBlock)
        assert b.level == 2
        assert b.text == "강남 소개"

    def test_h3(self):
        config = {**FULL_CONFIG, "post": [{"h3": "팁"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].level == 3


# ---------------------------------------------------------------------------
# Image — path interpolation
# ---------------------------------------------------------------------------

class TestImage:

    def test_static(self):
        config = {**FULL_CONFIG, "post": [{"image": "photo.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "images/photo.jpg"

    def test_keyword_in_path(self):
        config = {**FULL_CONFIG, "post": [{"image": "{keyword:region}.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "images/강남.jpg"

    def test_i_in_path(self):
        config = {**FULL_CONFIG, "post": [{"image": "{i}.jpg"}]}
        spec = build_spec(_combo(index=5), config)
        assert spec.body[0].blocks[0].path == "images/5.jpg"

    def test_dict_form_with_alt(self):
        config = {**FULL_CONFIG, "post": [
            {"image": {"path": "p.jpg", "alt": "{keyword:region} 외관"}},
        ]}
        spec = build_spec(_combo(), config)
        b = spec.body[0].blocks[0]
        assert b.path == "images/p.jpg"
        assert b.alt == "강남 외관"

    def test_dict_form_with_link(self):
        config = {**FULL_CONFIG, "post": [
            {"image": {"path": "p.jpg", "link": "tel:01012345678"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].link == "tel:01012345678"

    def test_string_form_has_no_link(self):
        config = {**FULL_CONFIG, "post": [{"image": "photo.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].link == ""


# ---------------------------------------------------------------------------
# Image path required — dynamic (post-interpolation) validation
# ---------------------------------------------------------------------------

class TestImagePathRequired:
    """interpolation 결과 path가 비어있으면 ConfigError."""

    def test_token_resolved_to_empty(self):
        """{keyword:region}이 빈 값으로 치환되어 path가 비면 실패."""
        from cli.config_loader import ConfigError
        config = {
            **FULL_CONFIG,
            "keywords": {"region": [""], "subject": ["수학"]},
            "post": [{"image": "{keyword:region}"}],
        }
        combo = Combo(values={"region": "", "subject": "수학"}, title_template=FULL_CONFIG["titles"][0], index=1)
        with pytest.raises(ConfigError, match="path.*interpolation"):
            build_spec(combo, config)

    def test_dict_path_resolved_to_empty(self):
        """dict 형식의 path 토큰도 interpolation 후 검증."""
        from cli.config_loader import ConfigError
        config = {
            **FULL_CONFIG,
            "keywords": {"region": [""], "subject": ["수학"]},
            "post": [{"image": {"path": "{keyword:region}", "link": "tel:..."}}],
        }
        combo = Combo(values={"region": "", "subject": "수학"}, title_template=FULL_CONFIG["titles"][0], index=1)
        with pytest.raises(ConfigError, match="path.*interpolation"):
            build_spec(combo, config)

    def test_featured_image_dynamic_empty(self):
        from cli.config_loader import ConfigError
        config = {
            **FULL_CONFIG,
            "keywords": {"region": [""], "subject": ["수학"]},
            "post": [{"featured_image": "{keyword:region}.jpg"}],
        }
        combo = Combo(values={"region": "", "subject": "수학"}, title_template=FULL_CONFIG["titles"][0], index=1)
        # "" + ".jpg" = ".jpg" — 이건 통과 (빈 값이 아니므로)
        spec = build_spec(combo, config)
        assert ".jpg" in spec.body[0].blocks[0].path


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------

class TestThumbnail:

    def test_static(self):
        config = {**FULL_CONFIG, "post": [{"featured_image": "thumb.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "images/thumb.jpg"

    def test_keyword_in_path(self):
        config = {**FULL_CONFIG, "post": [{"featured_image": "{keyword:region}.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "images/강남.jpg"

    def test_dict_form_with_overlay(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "overlay_text": "{keyword:region} 과외"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].overlay_text == "강남 과외"

    def test_dict_form_with_color(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "overlay_text": "텍스트", "overlay_color": "#FFD700"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].overlay_color == "#FFD700"

    def test_dict_form_with_background(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "overlay_text": "텍스트", "overlay_background": 0.6}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].overlay_background == 0.6

    def test_dict_form_with_position(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "overlay_text": "텍스트", "overlay_position": "bottom"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].overlay_position == "bottom"

    def test_dict_form_with_gps(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "gps": [37.497, 127.027]}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].exif_gps_lat == 37.497
        assert spec.body[0].blocks[0].exif_gps_lng == 127.027

    def test_dict_form_with_link(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "link": "tel:01012345678"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].link == "tel:01012345678"

    def test_dict_form_with_effects(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg", "effects": [
                {"region": "border:20", "effect": "brightness:0.5"},
                {"effect": "grayscale"},
            ]}},
        ]}
        spec = build_spec(_combo(), config)
        block = spec.body[0].blocks[0]
        assert len(block.effects) == 2
        assert block.effects[0].region == "border:20"
        assert block.effects[0].effect == "brightness:0.5"
        assert block.effects[1].region == "all"
        assert block.effects[1].effect == "grayscale"

    def test_default_effects_empty(self):
        config = {**FULL_CONFIG, "post": [
            {"featured_image": {"path": "t.jpg"}},
        ]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].effects == []


# ---------------------------------------------------------------------------
# Other blocks
# ---------------------------------------------------------------------------

class TestOtherBlocks:

    def test_quote(self):
        config = {**FULL_CONFIG, "post": [{"quote": "인용문"}]}
        spec = build_spec(_combo(), config)
        assert isinstance(spec.body[0].blocks[0], QuoteBlock)
        assert spec.body[0].blocks[0].text == "인용문"

    def test_quote_dict(self):
        config = {**FULL_CONFIG, "post": [{"quote": {"text": "인용", "attribution": "작가"}}]}
        spec = build_spec(_combo(), config)
        b = spec.body[0].blocks[0]
        assert b.text == "인용"
        assert b.attribution == "작가"

    def test_list(self):
        config = {**FULL_CONFIG, "post": [{"list": ["A", "B"]}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].items == ("A", "B")

    def test_list_interpolated(self):
        config = {**FULL_CONFIG, "post": [{"list": ["{keyword:region} 항목"]}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].items == ("강남 항목",)

    def test_divider(self):
        config = {**FULL_CONFIG, "post": ["divider"]}
        spec = build_spec(_combo(), config)
        assert isinstance(spec.body[0].blocks[0], DividerBlock)


# ---------------------------------------------------------------------------
# when — conditional blocks
# ---------------------------------------------------------------------------

class TestWhenCondition:

    def test_when_true_includes_block(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "강남 전용", "when": "{keyword:region} == 강남"},
        ]}
        spec = build_spec(_combo(values={"region": "강남", "subject": "수학"}), config)
        assert len(spec.body[0].blocks) == 1
        assert spec.body[0].blocks[0].prompt == "강남 전용"

    def test_when_false_excludes_block(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "강남 전용", "when": "{keyword:region} == 강남"},
        ]}
        spec = build_spec(_combo(values={"region": "서초", "subject": "수학"}), config)
        # Block excluded → falls back to default body
        blocks = spec.body[0].blocks
        assert all(b.prompt != "강남 전용" for b in blocks)

    def test_when_in_includes(self):
        config = {**FULL_CONFIG, "post": [
            {"image": "special.jpg", "when": "{keyword:region} in [강남, 서초]"},
            {"image": "default.jpg"},
        ]}
        spec = build_spec(_combo(values={"region": "강남", "subject": "수학"}), config)
        paths = [b.path for b in spec.body[0].blocks]
        assert "images/special.jpg" in paths

    def test_when_not_in_excludes(self):
        config = {**FULL_CONFIG, "post": [
            {"image": "special.jpg", "when": "{keyword:region} in [강남, 서초]"},
            {"image": "default.jpg"},
        ]}
        spec = build_spec(_combo(values={"region": "잠실", "subject": "수학"}), config)
        paths = [b.path for b in spec.body[0].blocks]
        assert "images/special.jpg" not in paths
        assert "images/default.jpg" in paths

    def test_no_when_always_included(self):
        config = {**FULL_CONFIG, "post": [{"paragraph": "항상 포함"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].prompt == "항상 포함"

    def test_when_not_in(self):
        config = {**FULL_CONFIG, "post": [
            {"paragraph": "기타 지역", "when": "{keyword:region} not in [강남, 서초]"},
        ]}
        spec = build_spec(_combo(values={"region": "잠실", "subject": "수학"}), config)
        assert spec.body[0].blocks[0].prompt == "기타 지역"


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

    def test_prepended(self):
        config = {**FULL_CONFIG, "assets": "./photos", "post": [{"image": "a.jpg"}]}
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "photos/a.jpg"

    def test_no_images_dir(self):
        config = {**FULL_CONFIG, "post": [{"image": "a.jpg"}]}
        del config["assets"]
        spec = build_spec(_combo(), config)
        assert spec.body[0].blocks[0].path == "a.jpg"


# ---------------------------------------------------------------------------
# Default body
# ---------------------------------------------------------------------------

class TestDefaultBody:

    def test_no_post(self):
        config = {**FULL_CONFIG}
        del config["post"]
        spec = build_spec(_combo(), config)
        assert len(spec.body[0].blocks) == 3
        assert all(isinstance(b, ParagraphBlock) for b in spec.body[0].blocks)


