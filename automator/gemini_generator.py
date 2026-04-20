"""
automator/gemini_generator.py
-------------------------------
GeminiGenerator — TextGenerator implementation backed by Gemini API.

In non-production environments, returns stub paragraphs (no API call).
"""

from __future__ import annotations

from typing import override

from automator.ports import TextGenerator
from automator.paragraph_generator import generate_paragraph


class GeminiGenerator(TextGenerator):
    """
    Delegates to generate_paragraph() which handles ENV switching internally.

    Args:
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var).
        model:   Gemini model name (defaults to gemini-flash-latest).
    """

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key
        self._model = model

    @override
    def generate(self, prompt: str) -> str:
        return generate_paragraph(
            prompt, api_key=self._api_key, model=self._model,
        )
