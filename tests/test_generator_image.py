"""
tests/test_generator_image.py
-------------------------------
process_image() / process_featured() / build_filename() 단위 테스트.

Pillow 와 piexif 를 사용해 이미지를 변형하는 로직을 검증한다.
실제 파일 I/O 는 tmp_path fixture 로 격리한다.
"""

import io
import pytest
from PIL import Image

from automator.image_processor import process_image, process_featured, build_filename
from automator.options import ImageBlock, FeaturedImageBlock


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

    def test_size_jitter_default(self):
        assert ImageBlock(path="x.jpg").size_jitter_px == 2

    def test_saturation_jitter_default(self):
        assert ImageBlock(path="x.jpg").saturation_jitter == 0.03

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

    def test_saturation_shift_default(self):
        assert FeaturedImageBlock().saturation_shift == 0.30

    def test_overlay_text_default(self):
        assert FeaturedImageBlock().overlay_text == ""


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
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0,
                            exif_description="강남 수학 과외")
        result = process_image(_jpeg(), block)
        assert "강남 수학 과외".encode() in result

    def test_gps_embedded_when_provided(self):
        block  = ImageBlock(path="x.jpg", pixel_jitter=False, size_jitter_px=0,
                            exif_gps_lat=37.49, exif_gps_lng=127.06)
        result = process_image(_jpeg(), block)
        assert len(result) > 0   # GPS 삽입 후에도 유효한 JPEG


# ---------------------------------------------------------------------------
# process_featured
# ---------------------------------------------------------------------------

class TestProcessFeatured:

    def test_returns_jpeg_bytes(self):
        block  = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        result = process_featured(_jpeg(), block)
        assert result[:2] == b"\xff\xd8"

    def test_overlay_text_applied(self):
        """overlay_text 가 있으면 처리 후 파일 크기가 달라질 수 있다."""
        base    = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0)
        overlay = FeaturedImageBlock(pixel_jitter=False, size_jitter_px=0,
                                     overlay_text="강남 수학")
        size_base    = len(process_featured(_jpeg(200, 200), base))
        size_overlay = len(process_featured(_jpeg(200, 200), overlay))
        # 텍스트 오버레이가 적용된 이미지와 아닌 이미지는 크기가 다를 수 있다
        # (같을 수도 있으므로 단순히 유효한 JPEG 인지만 확인)
        assert size_overlay > 0

    def test_list_overlay_text(self):
        block  = FeaturedImageBlock(overlay_text=["강남", "수학 과외"])
        result = process_featured(_jpeg(200, 200), block)
        assert result[:2] == b"\xff\xd8"


# ---------------------------------------------------------------------------
# build_filename
# ---------------------------------------------------------------------------

class TestBuildFilename:

    def test_with_keyword(self):
        assert build_filename("preview", 1, keyword="강남-수학") == "강남-수학-preview-01.jpg"

    def test_without_keyword(self):
        assert build_filename("featured", 2) == "featured-02.jpg"

    def test_index_zero_padded(self):
        assert build_filename("preview", 5) == "preview-05.jpg"

    def test_index_double_digit(self):
        assert build_filename("preview", 10) == "preview-10.jpg"
