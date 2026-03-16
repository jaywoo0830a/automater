"""
automator/image_processor.py
------------------------------
ImageProcessor — transforms images before upload for SEO purposes.

Pipeline per image
------------------
    process_preview(src_bytes, keyword)
        pixel_jitter  → randomly alter 1–3 pixels
        size_jitter   → resize by ±size_jitter_px
        exif          → embed description + GPS
        → JPEG bytes

    process_thumbnail(src_bytes, keyword)
        pixel_jitter  → same as above
        size_jitter   → same as above
        text_overlay  → draw thumbnail_text on the image
        exif          → embed description + GPS
        → JPEG bytes

Usage:
    from automator.options import ImageOption
    from automator.image_processor import ImageProcessor

    proc = ImageProcessor(ImageOption(
        pixel_jitter      = True,
        size_jitter_px    = 2,
        thumbnail_text    = "강남 수학 과외",
        exif_description  = "강남 수학 과외",
        exif_gps_lat      = 37.4942,
        exif_gps_lng      = 127.0617,
        filename_keyword  = "강남-수학-과외",
    ))

    preview_bytes   = proc.process_preview(raw_bytes, keyword="강남 수학 과외")
    thumbnail_bytes = proc.process_thumbnail(raw_bytes, keyword="강남 수학 과외")
    filename        = proc.build_filename("preview", index=1)
    # → "강남-수학-과외-preview-01.jpg"
"""

from __future__ import annotations

import io
import random
import struct
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from automator.options import ImageOption


# ---------------------------------------------------------------------------
# GPS conversion helpers
# ---------------------------------------------------------------------------

def _decimal_to_dms_rational(value: float) -> list[tuple[int, int]]:
    """
    Convert decimal degrees to DMS (degrees, minutes, seconds) as
    piexif-compatible rational tuples [(num, denom), ...].
    """
    abs_val  = abs(value)
    degrees  = int(abs_val)
    minutes  = int((abs_val - degrees) * 60)
    seconds  = round(((abs_val - degrees) * 60 - minutes) * 60 * 10000)
    return [(degrees, 1), (minutes, 1), (seconds, 10000)]


def _gps_ref(value: float, axis: str) -> bytes:
    """Return the GPS reference byte (N/S or E/W)."""
    if axis == "lat":
        return b"N" if value >= 0 else b"S"
    return b"E" if value >= 0 else b"W"


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

class ImageProcessor:
    """
    Applies SEO-optimised transformations to JPEG/PNG images.

    Args:
        option: ImageOption instance controlling the pipeline.
    """

    def __init__(self, option: ImageOption) -> None:
        self._opt = option

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_preview(self, src: bytes, keyword: str) -> bytes:
        """
        Apply pixel/size jitter and Exif metadata to a preview image.

        Args:
            src:     Raw image bytes (JPEG or PNG).
            keyword: Target keyword for Exif description fallback.

        Returns:
            Processed JPEG bytes.
        """
        img = Image.open(io.BytesIO(src)).convert("RGB")
        img = self._apply_size_jitter(img)
        img = self._apply_pixel_jitter(img)
        return self._encode_with_exif(img, keyword)

    def process_thumbnail(self, src: bytes, keyword: str) -> bytes:
        """
        Apply pixel/size jitter, text overlay, and Exif to a thumbnail image.

        Args:
            src:     Raw image bytes (JPEG or PNG).
            keyword: Target keyword for Exif description fallback.

        Returns:
            Processed JPEG bytes.
        """
        img = Image.open(io.BytesIO(src)).convert("RGB")
        img = self._apply_size_jitter(img)
        img = self._apply_pixel_jitter(img)
        img = self._apply_text_overlay(img)
        return self._encode_with_exif(img, keyword)

    def build_filename(self, role: str, index: int) -> str:
        """
        Build a keyword-rich filename for upload.

        Args:
            role:  "preview" or "thumbnail".
            index: 1-based image index within the post.

        Returns:
            e.g. "강남-수학-과외-preview-01.jpg"
        """
        kw   = self._opt.filename_keyword
        num  = f"{index:02d}"
        if kw:
            return f"{kw}-{role}-{num}.jpg"
        return f"{role}-{num}.jpg"

    # ------------------------------------------------------------------
    # Private pipeline steps
    # ------------------------------------------------------------------

    def _apply_pixel_jitter(self, img: Image.Image) -> Image.Image:
        """Randomly alter 1–3 pixels to change the image hash."""
        if not self._opt.pixel_jitter:
            return img

        pixels = img.load()
        w, h   = img.size
        count  = random.randint(1, 3)
        for _ in range(count):
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)
            r, g, b = pixels[x, y]
            # Shift each channel by ±1, clamped to 0–255
            pixels[x, y] = (
                max(0, min(255, r + random.choice([-1, 1]))),
                max(0, min(255, g + random.choice([-1, 1]))),
                max(0, min(255, b + random.choice([-1, 1]))),
            )
        return img

    def _apply_size_jitter(self, img: Image.Image) -> Image.Image:
        """Resize the image by ±size_jitter_px pixels."""
        n = self._opt.size_jitter_px
        if n == 0:
            return img

        w, h    = img.size
        delta_w = random.randint(-n, n)
        delta_h = random.randint(-n, n)
        new_w   = max(1, w + delta_w)
        new_h   = max(1, h + delta_h)

        if (new_w, new_h) == (w, h):
            return img

        return img.resize((new_w, new_h), Image.LANCZOS)

    def _apply_text_overlay(self, img: Image.Image) -> Image.Image:
        """Draw thumbnail_text over the image."""
        text = self._opt.thumbnail_text
        if not text:
            return img

        draw    = ImageDraw.Draw(img)
        w, h    = img.size
        color   = self._opt.thumbnail_text_color

        # Font size: ~6% of image width, minimum 14px
        font_size = max(14, int(w * 0.06))

        try:
            # Try system fonts common on Linux/Mac
            for font_path in (
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ):
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, font_size)
                    break
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Center the text
        bbox   = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x      = (w - text_w) // 2
        y      = (h - text_h) // 2

        # Thin shadow for readability
        shadow_offset = max(1, font_size // 20)
        shadow_color  = "#000000" if color.upper() in ("#FFFFFF", "#FFF") else "#FFFFFF"
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=color)

        return img

    def _encode_with_exif(self, img: Image.Image, keyword: str) -> bytes:
        """Encode image as JPEG and embed Exif metadata if configured."""
        buf = io.BytesIO()

        has_description = bool(self._opt.exif_description or keyword)
        has_gps         = self._opt.exif_gps_lat is not None and \
                          self._opt.exif_gps_lng is not None

        if not has_description and not has_gps:
            img.save(buf, format="JPEG", quality=92)
            return buf.getvalue()

        try:
            import piexif

            zeroth: dict = {}
            gps:    dict = {}

            # ImageDescription: prefer explicit description, fall back to keyword
            description = (self._opt.exif_description or keyword).encode("utf-8")
            if description:
                zeroth[piexif.ImageIFD.ImageDescription] = description

            # GPS
            if has_gps:
                lat = self._opt.exif_gps_lat
                lng = self._opt.exif_gps_lng
                gps[piexif.GPSIFD.GPSLatitudeRef]  = _gps_ref(lat, "lat")
                gps[piexif.GPSIFD.GPSLatitude]      = _decimal_to_dms_rational(lat)
                gps[piexif.GPSIFD.GPSLongitudeRef] = _gps_ref(lng, "lng")
                gps[piexif.GPSIFD.GPSLongitude]     = _decimal_to_dms_rational(lng)

            exif_dict  = {"0th": zeroth, "GPS": gps, "Exif": {}, "1st": {}}
            exif_bytes = piexif.dump(exif_dict)
            img.save(buf, format="JPEG", quality=92, exif=exif_bytes)

        except ImportError:
            # piexif not installed — save without Exif
            img.save(buf, format="JPEG", quality=92)

        return buf.getvalue()
