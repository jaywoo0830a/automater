"""
automator/local_processor.py
------------------------------
LocalImageProcessor — ImageProcessor implementation using Pillow.

Delegates to process_image in image_processor.py.
"""

from __future__ import annotations

from typing import Any, override

from automator.ports import ImageGenerator, ImageProcessor
from automator.image_processor import process_image


class LocalImageProcessor(ImageProcessor):
    """Pillow-based image processing with jitter, EXIF, overlay, layers."""

    def __init__(self, image_generator: ImageGenerator | None = None) -> None:
        self._image_generator = image_generator

    @override
    def process(self, raw: bytes, block: Any) -> bytes:
        return process_image(raw, block, image_generator=self._image_generator)
