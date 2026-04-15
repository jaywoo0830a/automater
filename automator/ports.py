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


class TitleChecker(ABC):
    """Check whether a title already exists on the target platform."""

    @abstractmethod
    def is_duplicate(self, title: str, query: str) -> bool:
        """Search for *query* and return True if *title* appears in results.

        Args:
            title: Full generated title to match against results.
            query: Keyword-only part used as the search query.
        """

    def close(self) -> None:  # noqa: B027
        """Release resources (optional)."""


class ImageGenerator(ABC):
    """Generate an image from a prompt. Returns PNG/JPEG bytes."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        width:  int | None = None,
        height: int | None = None,
        seed:   int | None = None,
        model:  str        = "",
    ) -> bytes | None:
        """Return image bytes, or None if generation failed."""


class SelectorSource(ABC):
    """Load platform-specific selector data."""

    @abstractmethod
    def load(self, name: str) -> Any:
        """Load and return a SelectorLoader-compatible object for ``name``."""
