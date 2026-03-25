"""
tests/unit/automator/test_exif_optimizer.py
---------------------------------------------
EXIF optimizer — injects realistic camera metadata into images.

Uses the `exif` package (not piexif) for cleaner attribute-style access.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image as PILImage

from automator.exif_optimizer import optimize_exif, DEVICE_POOL

KST = timezone(timedelta(hours=9))


def _jpeg(width=200, height=200, color=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Basic operation
# ---------------------------------------------------------------------------

class TestBasicOperation:

    def test_returns_valid_jpeg(self):
        result = optimize_exif(_jpeg())
        assert result[:2] == b"\xff\xd8"

    def test_output_differs_from_input(self):
        src = _jpeg()
        result = optimize_exif(src)
        assert result != src

    def test_disabled_returns_original(self):
        src = _jpeg()
        result = optimize_exif(src, enabled=False)
        assert result == src


# ---------------------------------------------------------------------------
# Device metadata
# ---------------------------------------------------------------------------

class TestDeviceMetadata:

    def test_make_is_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert img.has_exif
        assert img.make in [d["make"] for d in DEVICE_POOL]

    def test_model_is_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert img.model != ""

    def test_software_is_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert img.software != ""


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------

class TestTimestamps:

    def test_datetime_original_is_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert img.datetime_original != ""

    def test_datetime_digitized_is_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert img.datetime_digitized != ""


# ---------------------------------------------------------------------------
# GPS
# ---------------------------------------------------------------------------

class TestGPS:

    def test_gps_set_when_provided(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(), gps_lat=37.497, gps_lng=127.027)
        img = ExifImage(result)
        assert img.gps_latitude is not None
        assert img.gps_longitude is not None

    def test_gps_not_set_when_omitted(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        assert not hasattr(img, "gps_latitude") or img.get("gps_latitude") is None

    def test_gps_latitude_ref(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(), gps_lat=37.497, gps_lng=127.027)
        img = ExifImage(result)
        assert img.gps_latitude_ref == "N"
        assert img.gps_longitude_ref == "E"

    def test_gps_southern_hemisphere(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(), gps_lat=-33.8, gps_lng=151.2)
        img = ExifImage(result)
        assert img.gps_latitude_ref == "S"


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------

class TestDescription:

    def test_ascii_description_set(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(), description="gangnam math tutor")
        img = ExifImage(result)
        assert img.image_description == "gangnam math tutor"

    def test_korean_description_skipped(self):
        """Non-ASCII description is silently skipped (EXIF spec limitation)."""
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(), description="강남 수학 과외")
        img = ExifImage(result)
        desc = img.get("image_description", "")
        assert desc is None or desc == "" or "강남" not in str(desc)

    def test_description_not_set_when_omitted(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg())
        img = ExifImage(result)
        desc = img.get("image_description", "")
        assert desc == "" or desc is None


# ---------------------------------------------------------------------------
# Image dimensions
# ---------------------------------------------------------------------------

class TestDimensions:

    def test_pixel_dimensions_match_image(self):
        from exif import Image as ExifImage
        result = optimize_exif(_jpeg(300, 200))
        img = ExifImage(result)
        assert img.pixel_x_dimension == 300
        assert img.pixel_y_dimension == 200


# ---------------------------------------------------------------------------
# Device pool
# ---------------------------------------------------------------------------

class TestDevicePool:

    def test_pool_has_entries(self):
        assert len(DEVICE_POOL) >= 3

    def test_each_entry_has_required_keys(self):
        for device in DEVICE_POOL:
            assert "make" in device
            assert "model" in device
            assert "software" in device
