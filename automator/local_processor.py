"""
automator/local_processor.py
------------------------------
LocalImageProcessor — ImageProcessor implementation using Pillow.

Delegates to process_image in image_processor.py.
"""

from __future__ import annotations

from typing import Any

from automator.ports import ImageProcessor
from automator.image_processor import process_image


class LocalImageProcessor(ImageProcessor):
    """Pillow-based image processing with jitter, EXIF, overlay."""

    def process(self, raw: bytes, block: Any) -> bytes:
        return process_image(raw, block)
