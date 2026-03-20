"""
automator/local_processor.py
------------------------------
LocalImageProcessor — ImageProcessor implementation using Pillow.

Delegates to the existing process_image / process_featured / build_filename
functions in image_processor.py.
"""

from __future__ import annotations

from typing import Any

from automator.ports import ImageProcessor
from automator.image_processor import (
    process_image,
    process_featured,
    build_filename,
)


class LocalImageProcessor(ImageProcessor):
    """Pillow-based image processing with jitter, EXIF, overlay."""

    def process_body(self, raw: bytes, block: Any) -> bytes:
        return process_image(raw, block)

    def process_featured(self, raw: bytes, block: Any) -> bytes:
        return process_featured(raw, block)

    def build_filename(self, prefix: str, index: int, keyword: str) -> str:
        return build_filename(prefix, index, keyword)
