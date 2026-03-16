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

from automator.config import is_production

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """
    Raised when the Gemini API returns 429 RESOURCE_EXHAUSTED.

    Callers can catch this specifically to skip retrying, display a helpful
    message, or fall back to placeholder text — without masking other errors.

        try:
            paragraphs = gen.generate(count=3)
        except RateLimitError:
            # Daily free-tier quota exhausted — use placeholders
            paragraphs = ["(단락 생성 실패 — API 쿼터 초과)"] * 3
    """

# gemini-flash-latest: always points to the latest available Flash model.
# Use this alias to avoid hard-coding a specific version that may be blocked.
# Ref: https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = "gemini-flash-latest"

# ---------------------------------------------------------------------------
# Stub paragraphs — Universal Declaration of Human Rights (Korean)
# Used in dev/test environments instead of real Gemini API calls.
# ---------------------------------------------------------------------------

_STUB_PARAGRAPHS = [
    (
        "모든 사람은 태어날 때부터 자유롭고, 존엄성과 권리에 있어서 평등하다. "
        "사람은 이성과 양심을 부여받았으며, 서로에게 형제애의 정신으로 대해야 한다."
    ),
    (
        "모든 사람은 인종, 피부색, 성별, 언어, 종교, 정치적 또는 그 밖의 견해, "
        "출신 민족 또는 사회적 신분, 재산, 출생 또는 그 밖의 지위에 따른 "
        "어떠한 구별도 없이 이 선언에 규정된 모든 권리와 자유를 누릴 자격이 있다."
    ),
    (
        "모든 사람은 생명권과 신체의 자유와 안전을 누릴 권리가 있다."
    ),
    (
        "모든 사람은 어디에서나 법 앞에 인간으로서 인정받을 권리를 가진다."
    ),
    (
        "모든 사람은 자신의 나라 안에서 자유롭게 이동하고 거주지를 선택할 권리가 있다."
    ),
]


def _stub_generate(count: int) -> list[str]:
    """
    Return ``count`` stub paragraphs from the Universal Declaration of Human Rights.

    Cycles through _STUB_PARAGRAPHS so any count is supported.
    No external dependencies — always works offline.
    """
    return [
        _STUB_PARAGRAPHS[(i) % len(_STUB_PARAGRAPHS)]
        for i in range(count)
    ]

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
    Generates blog paragraphs — real or mock, depending on ENV.

    ENV behaviour
    -------------
    ENV=production  → calls Gemini API (real content, costs quota)
    ENV=dev | test  → returns stub paragraphs (UDHR Korean, no dependencies)

    This means you never have to touch test code or conftest to switch
    between real and mock content — just set ENV in .env.

    Args:
        prompt:  The user's content instruction (e.g. "대치동 수학 과외 홍보").
        api_key: Gemini API key. Defaults to GEMINI_API_KEY env var.
                 Only required when ENV=production.
        model:   Gemini model name. Defaults to GEMINI_MODEL env var.
    """

    def __init__(
        self,
        prompt:  str,
        api_key: str = "",
        model:   str = "",
    ) -> None:
        self._prompt      = prompt
        self._production  = is_production()
        self._api_key     = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model       = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL)

        if self._production and not self._api_key:
            raise ValueError(
                "Gemini API key is required in production. "
                "Set GEMINI_API_KEY in .env or pass api_key= explicitly."
            )

    def generate(self, count: int) -> list[str]:
        """
        Generate ``count`` paragraphs and return them as a list of strings.

        ENV=production  → calls Gemini API; all errors propagate to caller.
        ENV=dev | test  → returns stub paragraphs (UDHR Korean), no API call.

        Args:
            count: Number of paragraphs to generate.

        Returns:
            List of ``count`` paragraph strings.

        Raises:
            RateLimitError: When the API returns 429 RESOURCE_EXHAUSTED.
            Exception:      Any other API or parsing error — not swallowed.
        """
        if count <= 0:
            return []

        # Non-production: return stub paragraphs without any API call
        if not self._production:
            return _stub_generate(count)

        # Production: call real Gemini API — all errors propagate
        raw = self._call_api(count)
        return self._parse(raw, count)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_api(self, count: int) -> str:
        """
        Send the prompt to Gemini and return the raw response text.

        Raises:
            RateLimitError: When the API returns 429 RESOURCE_EXHAUSTED.
                            Callers can catch this to skip or retry gracefully.
        """
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]

        client = genai.Client(api_key=self._api_key)

        user_text = _USER_TEMPLATE.format(
            user_prompt=self._prompt,
            count=count,
        )

        try:
            response = client.models.generate_content(
                model=self._model,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=2048,
                ),
            )
        except Exception as exc:
            # Detect 429 RESOURCE_EXHAUSTED and re-raise as RateLimitError
            # so callers can handle quota exhaustion explicitly.
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                raise RateLimitError(
                    f"Gemini API rate limit exceeded: {msg}"
                ) from exc
            raise

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
