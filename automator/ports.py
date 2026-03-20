"""
automator/ports.py
-------------------
Abstract ports — dependency inversion boundaries.

Consumers depend on these ABCs. Concrete implementations are injected
at the composition root (main.py).

    TextGenerator    — prompt -> list[str]
    ImageProcessor   — raw bytes + options -> processed bytes
    SelectorSource   — name -> SelectorLoader-like object
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TextGenerator(ABC):
    """Generate text paragraphs from a prompt."""

    @abstractmethod
    def generate(self, prompt: str, count: int) -> list[str]:
        """Return ``count`` paragraphs for the given ``prompt``."""


class ImageProcessor(ABC):
    """Process raw image bytes with block-level options."""

    @abstractmethod
    def process_body(self, raw: bytes, block: Any) -> bytes:
        """Apply body-image transformations. Returns JPEG bytes."""

    @abstractmethod
    def process_featured(self, raw: bytes, block: Any) -> bytes:
        """Apply featured-image transformations. Returns JPEG bytes."""

    @abstractmethod
    def build_filename(self, prefix: str, index: int, keyword: str) -> str:
        """Build a deterministic upload filename."""


class SelectorSource(ABC):
    """Load platform-specific selector data."""

    @abstractmethod
    def load(self, name: str) -> Any:
        """Load and return a SelectorLoader-compatible object for ``name``."""
