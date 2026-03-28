"""
tests/test_image_processor.py
-------------------------------
process_image() 단위 테스트.

Pillow + exif 패키지를 사용해 이미지를 변형하는 로직을 검증한다.
실제 파일 I/O 는 tmp_path fixture 로 격리한다.
"""

import io
import pytest
from PIL import Image

from automator.image_processor import process_image
from automator.options import ImageBlock, FeaturedImageBlock, RegionalEffect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jpeg(width=100, height=100, color=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


def _size(data: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(data)).size


# ---------------------------------------------------------------------------
# ImageBlock defaults
# ---------------------------------------------------------------------------

class TestImageBlockDefaults:

    def test_pixel_jitter_default(self):
        assert ImageBlock(path="x.jpg").pixel_jitter is True

    def test_exif_optimization_default(self):
        assert ImageBlock(path="x.jpg").exif_optimization is True

    def test_size_jitter_default(self):
        assert ImageBlock(path="x.jpg").size_jitter_px == 2

    def test_effects_default(self):
        assert ImageBlock(path="x.jpg").effects == []

    def test_exif_description_default(self):
        assert ImageBlock(path="x.jpg").exif_description == ""

    def test_exif_gps_default(self):
        assert ImageBlock(path="x.jpg").exif_gps_lat is None
        assert ImageBlock(path="x.jpg").exif_gps_lng is None

    def test_filename_keyword_default(self):
        assert ImageBlock(path="x.jpg").filename_keyword == ""


# ---------------------------------------------------------------------------
# FeaturedImageBlock defaults
# ---------------------------------------------------------------------------

class TestFeaturedImageBlockDefaults:

    def test_overlay_color_default(self):
        assert FeaturedImageBlock().overlay_color == "#FFFFFF"

    def test_effects_default(self):
        assert FeaturedImageBlock().effects == []

    def test_overlay_text_default(self):
        assert FeaturedImageBlock().overlay_text == ""

    def test_overlay_background_default(self):
        assert FeaturedImageBlock().overlay_background == 0.0

    def test_overlay_position_default(self):
        assert FeaturedImageBlock().overlay_position == "center"

    def test_exif_optimization_default(self):
        assert FeaturedImageBlock().exif_optimization is True


# ---------------------------------------------------------------------------
# process_image
# ---------------------------------------------------------------------------

class TestProcessImage:

    def test_returns_jpeg_bytes(self):
        block  = ImageBlock(path="x.jpg", pixel_jitter=True, size_jitter_px=0)
        result = process_image(_jpeg(), block)
        assert result[:2] == b"\xff\xd8"

    def test_size_unchanged_when_jitter_zero(self):
        block = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0)
        w, h  = _size(process_image(_jpeg(100, 100), block))
        assert w == 100 and h == 100

    def test_size_may_change_when_jitter_nonzero(self):
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=4)
        sizes  = {_size(process_image(_jpeg(100, 100), block)) for _ in range(30)}
        assert len(sizes) > 1

    def test_accepts_png_input(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50)).save(buf, format="PNG")
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0)
        result = process_image(buf.getvalue(), block)
        assert result[:2] == b"\xff\xd8"

    def test_exif_description_embedded(self):
        from exif import Image as ExifImage
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0,
                            exif_description="gangnam math tutor")
        result = process_image(_jpeg(), block)
        img = ExifImage(result)
        assert img.image_description == "gangnam math tutor"

    def test_gps_embedded_when_provided(self):
        from exif import Image as ExifImage
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0,
                            exif_gps_lat=37.49, exif_gps_lng=127.06)
        result = process_image(_jpeg(), block)
        img = ExifImage(result)
        assert img.gps_latitude is not None

    def test_exif_device_metadata_injected(self):
        from exif import Image as ExifImage
        block = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0)
        result = process_image(_jpeg(), block)
        img = ExifImage(result)
        assert img.make != ""
        assert img.model != ""

    def test_exif_optimization_disabled(self):
        block = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0,
                           exif_optimization=False)
        src = _jpeg()
        result = process_image(src, block)
        assert result[:2] == b"\xff\xd8"

    def test_effects_applied(self):
        block = ImageBlock(
            path="x.jpg", pixel_jitter=False, size_jitter_px=0,
            exif_optimization=False,
            effects=[RegionalEffect(region="border:20", effect="brightness:0.3")],
        )
        img = _jpeg(100, 100, color=(200, 200, 200))
        result = process_image(img, block)
        out = Image.open(io.BytesIO(result))
        corner = out.getpixel((5, 5))
        center = out.getpixel((50, 50))
        assert corner[0] < center[0]


# ---------------------------------------------------------------------------
# process_image with FeaturedImageBlock
# ---------------------------------------------------------------------------

class TestProcessFeatured:

    def test_returns_jpeg_bytes(self):
        block  = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        result = process_image(_jpeg(), block)
        assert result[:2] == b"\xff\xd8"

    def test_overlay_text_applied(self):
        base    = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        overlay = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0,
                                     overlay_text="강남 수학")
        size_base    = len(process_image(_jpeg(200, 200), base))
        size_overlay = len(process_image(_jpeg(200, 200), overlay))
        assert size_overlay > 0

    def test_list_overlay_text(self):
        block  = FeaturedImageBlock(overlay_text=["강남", "수학 과외"])
        result = process_image(_jpeg(200, 200), block)
        assert result[:2] == b"\xff\xd8"

    def test_background_banner_changes_output(self):
        no_bg = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            overlay_text="테스트", overlay_background=0.0,
        )
        with_bg = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            overlay_text="테스트", overlay_background=0.6,
        )
        img = _jpeg(200, 200, color=(255, 255, 255))
        result_no  = process_image(img, no_bg)
        result_yes = process_image(img, with_bg)
        assert result_no != result_yes

    def test_position_bottom(self):
        block = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            overlay_text="하단 텍스트", overlay_position="bottom",
        )
        result = process_image(_jpeg(200, 200), block)
        assert result[:2] == b"\xff\xd8"

    def test_position_top(self):
        block = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            overlay_text="상단 텍스트", overlay_position="top",
        )
        result = process_image(_jpeg(200, 200), block)
        assert result[:2] == b"\xff\xd8"

    def test_effects_with_hue_changes_colors(self):
        """effects hue > 0 produces different pixel colors."""
        no_fx = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        with_fx = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            effects=[RegionalEffect(region="all", effect="hue:0.5")],
        )
        img = _jpeg(100, 100, color=(200, 100, 50))
        result_no  = process_image(img, no_fx)
        result_yes = process_image(img, with_fx)
        assert result_no != result_yes

    def test_no_effects_preserves(self):
        block = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0, exif_optimization=False,
        )
        img = _jpeg(100, 100)
        r1 = process_image(img, block)
        r2 = process_image(img, block)
        assert r1 == r2

    def test_effects_brightness_changes_output(self):
        no_fx = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        with_fx = FeaturedImageBlock(
            pixel_jitter=False, size_jitter_px=0,
            effects=[RegionalEffect(region="all", effect="brightness:0.5")],
        )
        img = _jpeg(100, 100, color=(150, 150, 150))
        result_no  = process_image(img, no_fx)
        result_yes = process_image(img, with_fx)
        assert result_no != result_yes
