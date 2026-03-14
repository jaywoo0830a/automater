"""
automator/paragraph_generator.py
----------------------------------
Generates blog paragraph text using the Google Gemini API.

Usage
-----
    from automator.paragraph_generator import ParagraphGenerator

    gen = ParagraphGenerator(api_key="...", prompt="대치동 수학 과외 홍보 블로그 단락 3개")
    paragraphs = gen.generate(count=3)
    # → ["단락1 텍스트", "단락2 텍스트", "단락3 텍스트"]

Design decisions
----------------
- One API call generates all N paragraphs at once (efficient, consistent tone).
- Response must be valid JSON array: ["단락1", "단락2", ...].
  If parsing fails, falls back to placeholder strings.
- Caller sets the prompt; this class only knows how to call the API and parse.
- api_key defaults to os.getenv("GEMINI_API_KEY") if not provided.

Requirements
------------
    pip install google-genai
"""

from __future__ import annotations

import json
import os
import re
import sys

# gemini-2.0-flash-lite: google-genai SDK (v1beta) + Free Tier 지원
# Ref: https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = "gemini-2.0-flash-lite"

_SYSTEM_PROMPT = """\
You are a Korean blog content writer specializing in education marketing.
Write natural, warm, and trustworthy paragraphs for a Naver blog post.
Each paragraph should be 3–5 sentences long and sound like a real person wrote it.
Do NOT use markdown, bullet points, or headings — plain text only.
"""

_USER_TEMPLATE = """\
{user_prompt}

단락 {count}개를 작성해주세요.
반드시 아래 JSON 배열 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.

["단락1 내용", "단락2 내용", ...]
"""


class ParagraphGenerator:
    """
    Calls the Gemini API to generate N blog paragraphs in one request.

    Args:
        prompt:  The user's content instruction (e.g. "대치동 수학 과외 홍보").
        api_key: Gemini API key. Defaults to GEMINI_API_KEY env var.
        model:   Gemini model name. Defaults to gemini-2.0-flash.
    """

    def __init__(
        self,
        prompt:  str,
        api_key: str = "",
        model:   str = "",
    ) -> None:
        self._prompt  = prompt
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model   = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL)

        if not self._api_key:
            raise ValueError(
                "Gemini API key is required. "
                "Set GEMINI_API_KEY in .env or pass api_key= explicitly."
            )

    def generate(self, count: int) -> list[str]:
        """
        Generate ``count`` paragraphs and return them as a list of strings.

        Falls back to placeholder strings if the API call fails or the
        response cannot be parsed as a JSON array.

        Args:
            count: Number of paragraphs to generate.

        Returns:
            List of ``count`` paragraph strings.
        """
        if count <= 0:
            return []

        try:
            raw = self._call_api(count)
            return self._parse(raw, count)
        except Exception as exc:
            print(
                f"[ParagraphGenerator] API error — falling back to placeholders: {exc}",
                file=sys.stderr,
            )
            return [f"(단락 {i} 생성 실패)" for i in range(1, count + 1)]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_api(self, count: int) -> str:
        """Send the prompt to Gemini and return the raw response text."""
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]

        client = genai.Client(api_key=self._api_key)

        user_text = _USER_TEMPLATE.format(
            user_prompt=self._prompt,
            count=count,
        )

        response = client.models.generate_content(
            model=self._model,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=2048,
            ),
        )
        return response.text

    def _parse(self, raw: str, count: int) -> list[str]:
        """
        Parse a JSON array from the raw API response.

        Strips markdown code fences if present, then JSON-parses.
        If parsing fails or the result has the wrong length, returns placeholders.
        """
        # Strip markdown code fences (```json ... ```)
        clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        # Extract the first JSON array found
        match = re.search(r"\[.*\]", clean, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON array found in response: {raw!r:.200s}")

        parsed = json.loads(match.group())

        if not isinstance(parsed, list):
            raise ValueError(f"Expected JSON array, got {type(parsed)}")

        # Pad or truncate to exactly ``count`` items
        result = [str(p) for p in parsed]
        while len(result) < count:
            result.append(f"(단락 {len(result) + 1} 생성 실패)")
        return result[:count]
