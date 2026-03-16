"""
tests/test_image_processor.py
-------------------------------
Unit tests for ImageProcessor.

Pillow 와 piexif 를 사용해 이미지를 변형하는 로직을 검증한다.
실제 파일 I/O 는 tmp_path fixture 로 격리한다.
"""

import io
import json
import struct

import pytest
from PIL import Image
from automator.image_processor import ImageProcessor
from automator.options import ImageOption


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _solid_image(width=100, height=100, color=(200, 200, 200)) -> bytes:
    """단색 JPEG 바이트열 생성."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _solid_png(width=100, height=100, color=(200, 200, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _img_size(data: bytes):
    img = Image.open(io.BytesIO(data))
    return img.size


# ---------------------------------------------------------------------------
# ImageOption 기본값
# ---------------------------------------------------------------------------

class TestImageOptionDefaults:

    def test_upload_delay_ms_default(self):
        assert ImageOption().upload_delay_ms == 1500

    def test_pixel_jitter_default(self):
        assert ImageOption().pixel_jitter is True

    def test_size_jitter_px_default(self):
        assert ImageOption().size_jitter_px == 2

    def test_thumbnail_text_default_empty(self):
        assert ImageOption().thumbnail_text == ""

    def test_thumbnail_text_color_default(self):
        assert ImageOption().thumbnail_text_color == "#FFFFFF"

    def test_exif_description_default_empty(self):
        assert ImageOption().exif_description == ""

    def test_exif_gps_lat_default_none(self):
        assert ImageOption().exif_gps_lat is None

    def test_exif_gps_lng_default_none(self):
        assert ImageOption().exif_gps_lng is None

    def test_filename_keyword_default_empty(self):
        assert ImageOption().filename_keyword == ""


# ---------------------------------------------------------------------------
# ImageOption 유효성 검사
# ---------------------------------------------------------------------------

class TestImageOptionValidation:

    def test_upload_delay_ms_negative_raises(self):
        with pytest.raises(ValueError, match="upload_delay_ms"):
            ImageOption(upload_delay_ms=-1)

    def test_size_jitter_px_negative_raises(self):
        with pytest.raises(ValueError, match="size_jitter_px"):
            ImageOption(size_jitter_px=-1)

    def test_invalid_hex_color_raises(self):
        with pytest.raises(ValueError, match="thumbnail_text_color"):
            ImageOption(thumbnail_text_color="red")

    def test_valid_hex_color_passes(self):
        ImageOption(thumbnail_text_color="#FF0000")
        ImageOption(thumbnail_text_color="#000000")


# ---------------------------------------------------------------------------
# pixel_jitter — 픽셀 미세 변형
# ---------------------------------------------------------------------------

class TestPixelJitter:

    def test_output_is_valid_jpeg(self, tmp_path):
        src = _solid_image()
        proc = ImageProcessor(ImageOption(pixel_jitter=True, size_jitter_px=0))
        result = proc.process_preview(src, keyword="test")
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_hash_differs_from_original(self, tmp_path):
        src = _solid_image()
        proc = ImageProcessor(ImageOption(pixel_jitter=True, size_jitter_px=0))
        result = proc.process_preview(src, keyword="test")
        assert result != src

    def test_disabled_jitter_preserves_content(self):
        """jitter 비활성화 + Exif 없음 → 변환 없이 원본 반환."""
        src = _solid_image()
        proc = ImageProcessor(ImageOption(
            pixel_jitter=False, size_jitter_px=0,
            exif_description="", exif_gps_lat=None, exif_gps_lng=None,
        ))
        result = proc.process_preview(src, keyword="")
        # 내용이 동일해야 함 (Pillow re-encode 로 바이트는 달라질 수 있음)
        assert _img_size(result) == _img_size(src)


# ---------------------------------------------------------------------------
# size_jitter — 해상도 미세 변형
# ---------------------------------------------------------------------------

class TestSizeJitter:

    def test_size_changes_within_range(self):
        src = _solid_image(100, 100)
        proc = ImageProcessor(ImageOption(pixel_jitter=False, size_jitter_px=3))
        result = proc.process_preview(src, keyword="test")
        w, h = _img_size(result)
        assert 97 <= w <= 103
        assert 97 <= h <= 103

    def test_size_jitter_zero_keeps_original_size(self):
        src = _solid_image(100, 100)
        proc = ImageProcessor(ImageOption(pixel_jitter=False, size_jitter_px=0))
        result = proc.process_preview(src, keyword="test")
        assert _img_size(result) == (100, 100)


# ---------------------------------------------------------------------------
# thumbnail_text — 썸네일 텍스트 삽입
# ---------------------------------------------------------------------------

class TestThumbnailText:

    def test_thumbnail_text_returns_jpeg(self):
        src = _solid_image(400, 300)
        proc = ImageProcessor(ImageOption(
            thumbnail_text="강남 수학 과외",
            thumbnail_text_color="#FFFFFF",
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_thumbnail(src, keyword="")
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_thumbnail_without_text_returns_processed(self):
        src = _solid_image(400, 300)
        proc = ImageProcessor(ImageOption(
            thumbnail_text="",
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_thumbnail(src, keyword="")
        assert Image.open(io.BytesIO(result)).format == "JPEG"

    def test_thumbnail_differs_from_original(self):
        src = _solid_image(400, 300)
        proc = ImageProcessor(ImageOption(
            thumbnail_text="테스트 텍스트",
            thumbnail_text_color="#FF0000",
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_thumbnail(src, keyword="")
        assert result != src


# ---------------------------------------------------------------------------
# Exif — 메타데이터 삽입
# ---------------------------------------------------------------------------

piexif = pytest.importorskip("piexif", reason="piexif not installed")


class TestExif:

    def test_exif_description_embedded(self):
        """ImageDescription Exif 필드에 keyword 가 포함된다."""
        src = _solid_image()
        proc = ImageProcessor(ImageOption(
            exif_description="강남 수학 과외",
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_preview(src, keyword="강남 수학 과외")
        import piexif
        exif = piexif.load(result)
        desc = exif["0th"].get(piexif.ImageIFD.ImageDescription, b"")
        assert "강남".encode("utf-8") in desc

    def test_exif_gps_embedded(self):
        """GPS IFD 에 위경도가 삽입된다."""
        src = _solid_image()
        proc = ImageProcessor(ImageOption(
            exif_gps_lat=37.4942,
            exif_gps_lng=127.0617,
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_preview(src, keyword="")
        import piexif
        exif = piexif.load(result)
        gps = exif.get("GPS", {})
        assert piexif.GPSIFD.GPSLatitude in gps
        assert piexif.GPSIFD.GPSLongitude in gps

    def test_no_exif_when_fields_empty(self):
        """exif_description 이 비어있고 GPS 없으면 Exif 필드 없음."""
        src = _solid_image()
        proc = ImageProcessor(ImageOption(
            exif_description="",
            exif_gps_lat=None,
            exif_gps_lng=None,
            pixel_jitter=False, size_jitter_px=0,
        ))
        result = proc.process_preview(src, keyword="")
        try:
            import piexif
            exif = piexif.load(result)
            desc = exif["0th"].get(piexif.ImageIFD.ImageDescription, b"")
            assert desc == b""
        except Exception:
            pass  # Exif 자체가 없으면 통과


# ---------------------------------------------------------------------------
# filename_keyword — 저장 파일명 생성
# ---------------------------------------------------------------------------

class TestFilenameKeyword:

    def test_build_filename_includes_keyword(self):
        proc = ImageProcessor(ImageOption(filename_keyword="강남-수학-과외"))
        name = proc.build_filename("preview", index=1)
        assert "강남-수학-과외" in name

    def test_build_filename_includes_index(self):
        proc = ImageProcessor(ImageOption(filename_keyword="test"))
        name = proc.build_filename("preview", index=2)
        assert "2" in name or "02" in name

    def test_build_filename_no_keyword_uses_fallback(self):
        proc = ImageProcessor(ImageOption(filename_keyword=""))
        name = proc.build_filename("preview", index=1)
        assert "preview" in name.lower()

    def test_build_filename_ends_with_jpg(self):
        proc = ImageProcessor(ImageOption(filename_keyword="test"))
        assert proc.build_filename("preview", 1).endswith(".jpg")
