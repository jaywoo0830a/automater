"""
automator/exif_optimizer.py
------------------------------
Inject realistic camera EXIF metadata into JPEG images.

Uses the `exif` package (attribute-style API) for clean read/write.
All fields are set to realistic values that mimic real smartphone photos.

Usage:
    from automator.exif_optimizer import optimize_exif

    optimized_bytes = optimize_exif(
        jpeg_bytes,
        description="강남 수학 과외",
        gps_lat=37.497,
        gps_lng=127.027,
    )

    # Disable optimization
    original_bytes = optimize_exif(jpeg_bytes, enabled=False)
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Device pool — common Korean smartphones
# ---------------------------------------------------------------------------

DEVICE_POOL = [
    {
        "make": "samsung",
        "model": "SM-S928N",
        "software": "S928NKSU4BXLA",
        "focal_length": 6.3,
        "f_number": 1.7,
    },
    {
        "make": "samsung",
        "model": "SM-S926N",
        "software": "S926NKSU4BXKA",
        "focal_length": 6.3,
        "f_number": 1.7,
    },
    {
        "make": "samsung",
        "model": "SM-S921N",
        "software": "S921NKSU4BXKA",
        "focal_length": 6.3,
        "f_number": 1.8,
    },
    {
        "make": "samsung",
        "model": "SM-A556N",
        "software": "A556NKSU2BXJ3",
        "focal_length": 4.6,
        "f_number": 1.8,
    },
    {
        "make": "Apple",
        "model": "iPhone 15 Pro Max",
        "software": "17.7.2",
        "focal_length": 6.765,
        "f_number": 1.78,
    },
    {
        "make": "Apple",
        "model": "iPhone 16 Pro",
        "software": "18.3.1",
        "focal_length": 6.765,
        "f_number": 1.78,
    },
    {
        "make": "Apple",
        "model": "iPhone 14 Pro",
        "software": "17.7.2",
        "focal_length": 6.86,
        "f_number": 1.78,
    },
]


# ---------------------------------------------------------------------------
# GPS helpers — decimal degrees to (degrees, minutes, seconds) tuple
# ---------------------------------------------------------------------------

def _decimal_to_dms(value: float) -> tuple[float, float, float]:
    """Convert decimal degrees to (degrees, minutes, seconds) tuple."""
    abs_val = abs(value)
    degrees = int(abs_val)
    minutes = int((abs_val - degrees) * 60)
    seconds = round(((abs_val - degrees) * 60 - minutes) * 60, 4)
    return (float(degrees), float(minutes), seconds)


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

_EXIF_DATETIME_FMT = "%Y:%m:%d %H:%M:%S"


def _random_recent_timestamp() -> str:
    """Generate a random daytime timestamp within the last 7 days (KST)."""
    now = datetime.now(tz=KST)
    days_ago = random.randint(0, 6)
    base = now - timedelta(days=days_ago)
    taken = base.replace(
        hour=random.randint(8, 20),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )
    return taken.strftime(_EXIF_DATETIME_FMT)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def optimize_exif(
    src: bytes,
    *,
    enabled: bool = True,
    description: str = "",
    gps_lat: float | None = None,
    gps_lng: float | None = None,
) -> bytes:
    """
    Inject realistic camera EXIF metadata into a JPEG image.

    When enabled=True (default), sets:
        - make, model, software (random device from pool)
        - datetime_original, datetime_digitized (random recent)
        - orientation (normal)
        - color_space (sRGB)
        - pixel_x_dimension, pixel_y_dimension (from image)
        - focal_length, f_number (from device)
        - exposure_time, photographic_sensitivity (random realistic)
        - image_description (if provided, ASCII-only — Korean is skipped)
        - GPS coordinates (if provided)

    Note: EXIF image_description is ASCII-only per spec. Korean keywords
    should use filename_keyword in DSL instead — file names support UTF-8.

    When enabled=False, returns src unchanged.

    Args:
        src:         JPEG bytes.
        enabled:     True to optimize, False to pass through.
        description: ASCII text for image_description (non-ASCII silently skipped).
        gps_lat:     GPS latitude (decimal degrees, + = N, - = S).
        gps_lng:     GPS longitude (decimal degrees, + = E, - = W).

    Returns:
        JPEG bytes with EXIF metadata.
    """
    if not enabled:
        return src

    try:
        from exif import Image as ExifImage, ColorSpace, Orientation
    except ImportError:
        return src

    try:
        from PIL import Image as PILImage
        import io
        pil_img = PILImage.open(io.BytesIO(src))
        width, height = pil_img.size
    except Exception:
        width, height = 0, 0

    img = ExifImage(src)
    device = random.choice(DEVICE_POOL)

    # Device metadata
    img.make = device["make"]
    img.model = device["model"]
    img.software = device["software"]

    # Timestamps
    timestamp = _random_recent_timestamp()
    img.datetime_original = timestamp
    img.datetime_digitized = timestamp

    # Orientation and color space
    img.orientation = Orientation.TOP_LEFT
    img.color_space = ColorSpace.SRGB

    # Image dimensions
    if width > 0 and height > 0:
        img.pixel_x_dimension = width
        img.pixel_y_dimension = height

    # Camera parameters
    img.focal_length = device["focal_length"]
    img.f_number = device["f_number"]

    exposure_options = [1/60, 1/125, 1/250, 1/500, 1/1000]
    img.exposure_time = random.choice(exposure_options)

    iso_options = [50, 100, 200, 400, 800]
    img.photographic_sensitivity = random.choice(iso_options)

    # Description (ASCII only — EXIF spec limitation)
    # Korean SEO keywords should use filename_keyword instead.
    if description:
        if all(ord(c) < 128 for c in description):
            img.image_description = description

    # GPS coordinates
    if gps_lat is not None and gps_lng is not None:
        img.gps_latitude = _decimal_to_dms(gps_lat)
        img.gps_latitude_ref = "N" if gps_lat >= 0 else "S"
        img.gps_longitude = _decimal_to_dms(gps_lng)
        img.gps_longitude_ref = "E" if gps_lng >= 0 else "W"

    return img.get_file()
