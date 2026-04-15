"""
tests/unit/automator/test_image_processor_layers.py
------------------------------------------------------
Layer composition pipeline in image_processor.
"""

import io

import pytest
from PIL import Image

from automator.image_processor import process_image
from automator.options import (
    AILayer,
    EffectLayer,
    FeaturedImageBlock,
    ImageBlock,
    ImageLayer,
)
from automator.ports import ImageGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _png_bytes(color: tuple[int, int, int], size: tuple[int, int] = (100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(color: tuple[int, int, int], size: tuple[int, int] = (200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


class _StubGenerator(ImageGenerator):
    def __init__(self, payload: bytes | None, raises: Exception | None = None) -> None:
        self.payload = payload
        self.raises = raises
        self.calls: list[dict] = []

    def generate(self, prompt, *, width=None, height=None, seed=None, model=""):
        self.calls.append(dict(prompt=prompt, width=width, height=height, seed=seed, model=model))
        if self.raises:
            raise self.raises
        return self.payload


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAILayer:
    def test_ai_layer_invokes_generator(self):
        gen = _StubGenerator(_png_bytes((255, 0, 0)))
        block = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="a cat", opacity=0.5, width=50, height=50),),
        )
        out = process_image(_jpeg_bytes((0, 0, 255)), block, image_generator=gen)

        assert len(gen.calls) == 1
        assert gen.calls[0]["prompt"] == "a cat"
        assert gen.calls[0]["width"] == 50
        assert gen.calls[0]["height"] == 50
        assert out  # produced a JPEG

    def test_ai_layer_default_size_uses_base_size(self):
        gen = _StubGenerator(_png_bytes((255, 0, 0)))
        block = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="hi"),),
            pixel_jitter=False, size_jitter_px=0,
        )
        process_image(_jpeg_bytes((0, 0, 255), size=(321, 123)), block, image_generator=gen)
        assert gen.calls[0]["width"] == 321
        assert gen.calls[0]["height"] == 123

    def test_ai_layer_generator_returns_none_falls_back(self):
        gen = _StubGenerator(None)
        base = _jpeg_bytes((0, 0, 255))
        block = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="x"),),
            pixel_jitter=False,
            size_jitter_px=0,
            exif_optimization=False,
        )
        out = process_image(base, block, image_generator=gen)
        # output is still a valid image (base survived)
        Image.open(io.BytesIO(out)).verify()

    def test_ai_layer_generator_raises_falls_back(self):
        gen = _StubGenerator(None, raises=RuntimeError("boom"))
        block = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="x"),),
            pixel_jitter=False,
            size_jitter_px=0,
            exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255)), block, image_generator=gen)
        Image.open(io.BytesIO(out)).verify()

    def test_ai_layer_without_generator_is_noop(self):
        block = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="x"),),
            pixel_jitter=False,
            size_jitter_px=0,
            exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255)), block, image_generator=None)
        Image.open(io.BytesIO(out)).verify()

    def test_opacity_blends_toward_base(self):
        # red AI layer at full opacity → output near red
        # red AI layer at 0.0 opacity → output stays blue
        base = _jpeg_bytes((0, 0, 255), size=(50, 50))
        gen_full = _StubGenerator(_png_bytes((255, 0, 0), size=(50, 50)))
        gen_zero = _StubGenerator(_png_bytes((255, 0, 0), size=(50, 50)))

        block_full = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="x", opacity=1.0, fit="stretch"),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        block_zero = FeaturedImageBlock(
            path="ignored",
            layers=(AILayer(prompt="x", opacity=0.0, fit="stretch"),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )

        out_full = process_image(base, block_full, image_generator=gen_full)
        out_zero = process_image(base, block_zero, image_generator=gen_zero)

        px_full = Image.open(io.BytesIO(out_full)).getpixel((25, 25))
        px_zero = Image.open(io.BytesIO(out_zero)).getpixel((25, 25))

        assert px_full[0] > px_full[2], f"full opacity should be red-dominant: {px_full}"
        assert px_zero[2] > px_zero[0], f"zero opacity should be blue-dominant: {px_zero}"


class TestImageLayer:
    def test_image_layer_composited(self, tmp_path):
        overlay_path = tmp_path / "overlay.png"
        Image.new("RGB", (50, 50), (0, 255, 0)).save(overlay_path)

        block = FeaturedImageBlock(
            path="ignored",
            layers=(ImageLayer(path=str(overlay_path), fit="stretch", opacity=1.0),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255), size=(50, 50)), block)
        px = Image.open(io.BytesIO(out)).getpixel((25, 25))
        assert px[1] > px[2], f"green overlay should dominate: {px}"

    def test_image_layer_missing_file_skipped(self):
        block = FeaturedImageBlock(
            path="ignored",
            layers=(ImageLayer(path="/nonexistent/xyz.png"),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255)), block)
        Image.open(io.BytesIO(out)).verify()


class TestEffectLayer:
    def test_effect_layer_grayscale(self):
        block = FeaturedImageBlock(
            path="ignored",
            layers=(EffectLayer(region="all", effect="grayscale"),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((200, 50, 10), size=(20, 20)), block)
        px = Image.open(io.BytesIO(out)).getpixel((10, 10))
        # grayscale → R == G == B (within jpeg noise)
        assert abs(px[0] - px[1]) <= 3 and abs(px[1] - px[2]) <= 3, px


class TestLayerOrdering:
    def test_order_preserved(self):
        """Layers apply in declared order — later layers cover earlier ones."""
        gen = _StubGenerator(_png_bytes((255, 0, 0), size=(50, 50)))
        # AI (red, full) → EffectLayer grayscale
        block = FeaturedImageBlock(
            path="ignored",
            layers=(
                AILayer(prompt="x", opacity=1.0, fit="stretch"),
                EffectLayer(region="all", effect="grayscale"),
            ),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255), size=(50, 50)), block, image_generator=gen)
        px = Image.open(io.BytesIO(out)).getpixel((25, 25))
        # after grayscale over red, channels should be equal
        assert abs(px[0] - px[1]) <= 3 and abs(px[1] - px[2]) <= 3, px


class TestEmptyLayers:
    def test_no_layers_is_unchanged_path(self):
        block = FeaturedImageBlock(path="ignored")
        out = process_image(_jpeg_bytes((100, 100, 100)), block)
        Image.open(io.BytesIO(out)).verify()

    def test_image_block_supports_layers(self):
        gen = _StubGenerator(_png_bytes((255, 0, 0)))
        block = ImageBlock(
            path="ignored",
            layers=(AILayer(prompt="hi"),),
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        out = process_image(_jpeg_bytes((0, 0, 255)), block, image_generator=gen)
        Image.open(io.BytesIO(out)).verify()
        assert len(gen.calls) == 1
