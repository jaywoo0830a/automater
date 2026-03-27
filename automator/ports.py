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
    """Generate a text paragraph from a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return a single paragraph for the given ``prompt``."""


class ImageProcessor(ABC):
    """Process raw image bytes with block-level options."""

    @abstractmethod
    def process(self, raw: bytes, block: Any) -> bytes:
        """Apply transformations described by *block*. Returns JPEG bytes."""


class SelectorSource(ABC):
    """Load platform-specific selector data."""

    @abstractmethod
    def load(self, name: str) -> Any:
        """Load and return a SelectorLoader-compatible object for ``name``."""
