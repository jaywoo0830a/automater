"""
automator/stubs.py
-------------------
Test doubles for ports.  No external dependencies.

    StubTextGenerator   — returns fixed paragraphs
    NoopImageProcessor  — returns input bytes unchanged
    DictSelectorSource  — resolves from an in-memory dict
"""

from __future__ import annotations

from typing import Any

from automator.ports import TextGenerator, ImageProcessor, SelectorSource
from automator.paragraph_generator import _STUB_PARAGRAPHS


# ---------------------------------------------------------------------------
# StubTextGenerator
# ---------------------------------------------------------------------------

class StubTextGenerator(TextGenerator):
    """Return canned paragraphs. Cycles UDHR stubs by default."""

    def __init__(self, paragraphs: list[str] | None = None) -> None:
        self._paragraphs = paragraphs or list(_STUB_PARAGRAPHS)

    def generate(self, prompt: str, count: int) -> list[str]:
        return [
            self._paragraphs[i % len(self._paragraphs)]
            for i in range(count)
        ]


# ---------------------------------------------------------------------------
# NoopImageProcessor
# ---------------------------------------------------------------------------

class NoopImageProcessor(ImageProcessor):
    """Return bytes unchanged.  For dry-run and unit tests."""

    def process_body(self, raw: bytes, block: Any) -> bytes:
        return raw

    def process_featured(self, raw: bytes, block: Any) -> bytes:
        return raw

    def build_filename(self, prefix: str, index: int, keyword: str) -> str:
        safe = keyword.replace(" ", "-") if keyword else "image"
        return f"{prefix}_{index:03d}_{safe}.jpg"


# ---------------------------------------------------------------------------
# DictSelectorSource
# ---------------------------------------------------------------------------

class DictSelectorSource(SelectorSource):
    """Resolve selectors from an in-memory dict. For tests only."""

    def __init__(self, loaders: dict[str, Any]) -> None:
        self._loaders = loaders

    def load(self, name: str) -> Any:
        if name not in self._loaders:
            raise FileNotFoundError(
                f"DictSelectorSource has no entry for {name!r}. "
                f"Available: {list(self._loaders.keys())}"
            )
        return self._loaders[name]
