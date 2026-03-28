"""
tests/unit/automator/test_region_effect.py
------------------------------------------
region_effect.py 단위 테스트.
"""

import io
import pytest
from PIL import Image

from automator.region_effect import apply_regional_effect


def _rgb_img(width=100, height=100, color=(128, 128, 128)) -> Image.Image:
    return Image.new("RGB", (width, height), color)


class TestBrightness:

    def test_darken_all(self):
        img = _rgb_img(color=(200, 200, 200))
        result = apply_regional_effect(img, "all", "brightness:0.5")
        assert result.getpixel((50, 50))[0] < 200

    def test_brighten_region_only(self):
        img = _rgb_img(color=(100, 100, 100))
        result = apply_regional_effect(img, "top:50%", "brightness:2.0")
        top_pixel = result.getpixel((50, 10))
        bottom_pixel = result.getpixel((50, 90))
        assert top_pixel[0] > bottom_pixel[0]


class TestSaturation:

    def test_desaturate(self):
        img = _rgb_img(color=(200, 100, 50))
        result = apply_regional_effect(img, "all", "saturation:0.0")
        r, g, b = result.getpixel((50, 50))
        # fully desaturated → r ≈ g ≈ b
        assert abs(r - g) < 5 and abs(g - b) < 5


class TestHue:

    def test_hue_shift_changes_color(self):
        img = _rgb_img(color=(255, 0, 0))
        result = apply_regional_effect(img, "all", "hue:0.33")
        r, g, b = result.getpixel((50, 50))
        # red shifted → no longer purely red
        assert g > 50 or b > 50


class TestBlur:

    def test_blur_smooths(self):
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        # draw a white dot
        img.putpixel((50, 50), (255, 255, 255))
        result = apply_regional_effect(img, "all", "blur:5")
        # the dot should spread
        assert result.getpixel((50, 50))[0] < 255
        assert result.getpixel((51, 50))[0] > 0


class TestTint:

    def test_tint_rgb(self):
        img = _rgb_img(color=(255, 255, 255))
        result = apply_regional_effect(img, "all", "tint:255,0,0,128")
        r, g, b = result.getpixel((50, 50))
        assert r > g  # red tint applied

    def test_tint_3_values_uses_default_alpha(self):
        img = _rgb_img(color=(255, 255, 255))
        result = apply_regional_effect(img, "all", "tint:0,0,255")
        r, g, b = result.getpixel((50, 50))
        assert b > r  # blue tint

    def test_tint_bad_values(self):
        img = _rgb_img()
        with pytest.raises(ValueError):
            apply_regional_effect(img, "all", "tint:255,0")


class TestGrayscale:

    def test_grayscale(self):
        img = _rgb_img(color=(200, 100, 50))
        result = apply_regional_effect(img, "all", "grayscale")
        r, g, b = result.getpixel((50, 50))
        assert r == g == b


class TestRegionalIsolation:

    def test_border_only_affects_border(self):
        img = _rgb_img(color=(200, 200, 200))
        result = apply_regional_effect(img, "border:20", "brightness:0.1")
        corner = result.getpixel((5, 5))
        center = result.getpixel((50, 50))
        # corner darkened, center untouched
        assert corner[0] < center[0]
        assert center == (200, 200, 200)


class TestRangeRandomization:

    def test_brightness_range(self):
        """brightness:0.1 ~ 0.5 → 어두워짐 (원본 128보다 작아야)."""
        img = _rgb_img(color=(128, 128, 128))
        result = apply_regional_effect(img, "all", "brightness:0.1 ~ 0.5")
        assert result.getpixel((50, 50))[0] < 128

    def test_blur_range(self):
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        img.putpixel((50, 50), (255, 255, 255))
        result = apply_regional_effect(img, "all", "blur:3 ~ 10")
        assert result.getpixel((50, 50))[0] < 255

    def test_saturation_range(self):
        img = _rgb_img(color=(200, 100, 50))
        result = apply_regional_effect(img, "all", "saturation:0.0 ~ 0.1")
        r, g, b = result.getpixel((50, 50))
        # nearly desaturated
        assert abs(r - g) < 30

    def test_hue_range(self):
        img = _rgb_img(color=(255, 0, 0))
        result = apply_regional_effect(img, "all", "hue:0.2 ~ 0.4")
        r, g, b = result.getpixel((50, 50))
        assert g > 50 or b > 50

    def test_tint_range_alpha(self):
        img = _rgb_img(color=(255, 255, 255))
        result = apply_regional_effect(img, "all", "tint:255,0,0,100 ~ 200")
        r, g, b = result.getpixel((50, 50))
        assert r > g

    def test_combined_region_and_effect_range(self):
        """region과 effect 양쪽 모두 범위."""
        img = _rgb_img(color=(200, 200, 200))
        result = apply_regional_effect(img, "border:10 ~ 30", "brightness:0.1 ~ 0.3")
        # corner darkened, center untouched
        assert result.getpixel((0, 0))[0] < 200
        assert result.getpixel((50, 50)) == (200, 200, 200)


class TestUnknownEffect:

    def test_unknown_raises(self):
        img = _rgb_img()
        with pytest.raises(ValueError, match="Unknown effect"):
            apply_regional_effect(img, "all", "sepia:1.0")
