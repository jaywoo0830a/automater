"""
tests/unit/cli/test_layer_spec.py
----------------------------------
Layer DSL parsing.
"""

import pytest

from cli.config_loader import ConfigError
from cli.layer_spec import (
    AILayer,
    EffectLayer,
    ImageLayer,
    parse_layers,
)


def _ctx(**overrides):
    base = dict(
        values={"region": "강남", "topic": "수학"},
        pools={"mood": ["차분한", "밝은"]},
        images_dir="images",
        index=1,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Shape / discriminator
# ---------------------------------------------------------------------------

class TestShape:
    def test_none_returns_empty(self):
        assert parse_layers(None, **_ctx()) == ()

    def test_non_list_raises(self):
        with pytest.raises(ConfigError, match="리스트"):
            parse_layers({"type": "ai"}, **_ctx())

    def test_entry_not_dict_raises(self):
        with pytest.raises(ConfigError, match=r"layers\[0\].*dict"):
            parse_layers(["not-a-dict"], **_ctx())

    def test_missing_type_raises(self):
        with pytest.raises(ConfigError, match="type"):
            parse_layers([{"prompt": "x"}], **_ctx())

    def test_unknown_type_raises(self):
        with pytest.raises(ConfigError, match="알 수 없는"):
            parse_layers([{"type": "bogus"}], **_ctx())

    def test_preserves_order(self):
        raw = [
            {"type": "ai", "prompt": "a"},
            {"type": "effect", "effect": "grayscale"},
            {"type": "image", "path": "x.png"},
        ]
        layers = parse_layers(raw, **_ctx())
        assert isinstance(layers[0], AILayer)
        assert isinstance(layers[1], EffectLayer)
        assert isinstance(layers[2], ImageLayer)


# ---------------------------------------------------------------------------
# AILayer
# ---------------------------------------------------------------------------

class TestAILayer:
    def test_minimal(self):
        layers = parse_layers([{"type": "ai", "prompt": "hello"}], **_ctx())
        ai = layers[0]
        assert isinstance(ai, AILayer)
        assert ai.prompt == "hello"
        assert ai.opacity == 1.0
        assert ai.blend == "normal"
        assert ai.fit == "cover"
        assert ai.provider == "pollinations"
        assert ai.model == ""
        assert ai.seed is None
        assert ai.width is None
        assert ai.height is None

    def test_full(self):
        raw = [{
            "type": "ai",
            "prompt": "cats",
            "opacity": 0.1,
            "blend": "multiply",
            "fit": "contain",
            "provider": "pollinations",
            "model": "flux",
            "seed": 42,
            "width": 1024,
            "height": 768,
        }]
        ai = parse_layers(raw, **_ctx())[0]
        assert ai.opacity == 0.1
        assert ai.blend == "multiply"
        assert ai.fit == "contain"
        assert ai.model == "flux"
        assert ai.seed == 42
        assert ai.width == 1024
        assert ai.height == 768

    def test_prompt_interpolation(self):
        raw = [{"type": "ai", "prompt": "{keyword:topic} {pool:mood}"}]
        ai = parse_layers(raw, **_ctx())[0]
        assert "수학" in ai.prompt
        assert any(m in ai.prompt for m in ("차분한", "밝은"))

    def test_empty_prompt_raises(self):
        with pytest.raises(ConfigError, match="prompt"):
            parse_layers([{"type": "ai", "prompt": ""}], **_ctx())

    def test_opacity_out_of_range(self):
        with pytest.raises(ConfigError, match="opacity"):
            parse_layers([{"type": "ai", "prompt": "x", "opacity": 1.5}], **_ctx())

    def test_opacity_non_numeric(self):
        with pytest.raises(ConfigError, match="숫자"):
            parse_layers([{"type": "ai", "prompt": "x", "opacity": "hi"}], **_ctx())

    def test_unknown_blend(self):
        with pytest.raises(ConfigError, match="blend"):
            parse_layers([{"type": "ai", "prompt": "x", "blend": "weird"}], **_ctx())

    def test_unknown_fit(self):
        with pytest.raises(ConfigError, match="fit"):
            parse_layers([{"type": "ai", "prompt": "x", "fit": "weird"}], **_ctx())

    def test_seed_non_int(self):
        with pytest.raises(ConfigError, match="seed"):
            parse_layers([{"type": "ai", "prompt": "x", "seed": "abc"}], **_ctx())


# ---------------------------------------------------------------------------
# ImageLayer
# ---------------------------------------------------------------------------

class TestImageLayer:
    def test_minimal(self):
        img = parse_layers([{"type": "image", "path": "w.png"}], **_ctx())[0]
        assert isinstance(img, ImageLayer)
        assert img.path == "images/w.png"
        assert img.opacity == 1.0

    def test_path_interpolation(self):
        raw = [{"type": "image", "path": "{keyword:region}.png"}]
        img = parse_layers(raw, **_ctx())[0]
        assert img.path == "images/강남.png"

    def test_full(self):
        raw = [{
            "type": "image",
            "path": "w.png",
            "opacity": 0.3,
            "blend": "screen",
            "fit": "tile",
        }]
        img = parse_layers(raw, **_ctx())[0]
        assert img.opacity == 0.3
        assert img.blend == "screen"
        assert img.fit == "tile"

    def test_empty_path_raises(self):
        with pytest.raises(ConfigError, match="path"):
            parse_layers([{"type": "image", "path": ""}], **_ctx())

    def test_no_images_dir(self):
        img = parse_layers(
            [{"type": "image", "path": "w.png"}],
            **_ctx(images_dir=""),
        )[0]
        assert img.path == "w.png"


# ---------------------------------------------------------------------------
# EffectLayer
# ---------------------------------------------------------------------------

class TestEffectLayer:
    def test_minimal(self):
        fx = parse_layers([{"type": "effect", "effect": "grayscale"}], **_ctx())[0]
        assert isinstance(fx, EffectLayer)
        assert fx.region == "all"
        assert fx.effect == "grayscale"

    def test_with_region(self):
        raw = [{"type": "effect", "region": "border:20", "effect": "brightness:0.5"}]
        fx = parse_layers(raw, **_ctx())[0]
        assert fx.region == "border:20"
        assert fx.effect == "brightness:0.5"

    def test_empty_effect_raises(self):
        with pytest.raises(ConfigError, match="effect"):
            parse_layers([{"type": "effect", "region": "all"}], **_ctx())

    def test_strips_quotes(self):
        raw = [{"type": "effect", "region": "'border:10'", "effect": '"grayscale"'}]
        fx = parse_layers(raw, **_ctx())[0]
        assert fx.region == "border:10"
        assert fx.effect == "grayscale"
