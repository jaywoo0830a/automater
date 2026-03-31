"""
automator/paragraph_generator.py
----------------------------------
Paragraph generation functions.

    generate_paragraph(prompt)  -> str

ENV=production  -> calls Gemini API
ENV=dev | test  -> returns stub paragraphs (no dependencies)

No class — prompt in, paragraphs out.
"""

from __future__ import annotations

import json
import os
import re

from automator.config import is_production


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when the Gemini API returns 429 RESOURCE_EXHAUSTED."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMINI_MODEL = "gemini-flash-latest"

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
    "모든 사람은 생명권과 신체의 자유와 안전을 누릴 권리가 있다.",
    "모든 사람은 어디에서나 법 앞에 인간으로서 인정받을 권리를 가진다.",
    "모든 사람은 자신의 나라 안에서 자유롭게 이동하고 거주지를 선택할 권리가 있다.",
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_paragraph(
    prompt: str,
    api_key: str = "",
    model: str = "",
) -> str:
    """
    Generate a single paragraph from ``prompt``.

    ENV=production  -> calls Gemini API; errors propagate.
    ENV=dev | test  -> returns a stub paragraph, no API call.

    Args:
        prompt:  Content instruction (e.g. "대치동 수학 과외 홍보").
        api_key: Gemini API key. Defaults to GEMINI_API_KEY env var.
        model:   Gemini model name. Defaults to GEMINI_MODEL.

    Returns:
        A single paragraph string.

    Raises:
        RateLimitError: API returns 429 RESOURCE_EXHAUSTED.
    """
    if not is_production():
        return _stub_generate(1)[0]

    resolved_key = api_key or os.getenv("GEMINI_API_KEY", "")
    resolved_model = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL)

    if not resolved_key:
        raise ValueError(
            "Gemini API key is required in production. "
            "Set GEMINI_API_KEY in .env or pass api_key= explicitly."
        )

    raw = _call_api(prompt, 1, resolved_key, resolved_model)
    return _parse(raw, 1)[0]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _stub_generate(count: int) -> list[str]:
    """Return ``count`` stub paragraphs (UDHR Korean). Cycles if needed."""
    return [
        _STUB_PARAGRAPHS[i % len(_STUB_PARAGRAPHS)]
        for i in range(count)
    ]


def _call_api(prompt: str, count: int, api_key: str, model: str) -> str:
    """Send the prompt to Gemini and return the raw response text."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    user_text = _USER_TEMPLATE.format(user_prompt=prompt, count=count)

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=65536,
            ),
        )
    except Exception as exc:
        msg = str(exc)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise RateLimitError(
                f"Gemini API rate limit exceeded: {msg}"
            ) from exc
        raise

    return response.text


def _parse(raw: str, count: int) -> list[str]:
    """
    Parse a JSON array from the raw API response.

    Handles:
        - Markdown fences around JSON
        - Literal newlines inside JSON strings (Gemini quirk)
        - Truncated responses (max_output_tokens hit mid-string)
        - Gemini splitting one paragraph into many array elements:
          when count=1 but API returns N elements, join them all
    """
    clean = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    sanitized = _escape_newlines_in_json(clean)

    parsed = _try_parse_json_array(sanitized)

    if parsed is not None:
        return _fit_to_count(parsed, count)

    raise ValueError(f"No JSON array found in response: {raw!r:.200s}")


def _try_parse_json_array(text: str) -> list[str] | None:
    """Try to extract a JSON string array from text. Returns None on failure."""
    # Exact match
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(p) for p in parsed if str(p).strip()]
        except json.JSONDecodeError:
            pass

    # Truncated array repair
    bracket = text.find("[")
    if bracket >= 0:
        fragment = text[bracket:]
        if fragment.count('"') % 2 == 1:
            fragment += '"'
        if not fragment.rstrip().endswith("]"):
            fragment = fragment.rstrip().rstrip(",") + "]"
        try:
            parsed = json.loads(fragment)
            if isinstance(parsed, list):
                return [str(p) for p in parsed if str(p).strip()]
        except json.JSONDecodeError:
            pass

    return None


def _fit_to_count(paragraphs: list[str], count: int) -> list[str]:
    """
    Fit parsed paragraphs to the requested count.

    When count=1 but Gemini returned multiple elements (common for
    long-form prompts), join them all into one text with paragraph
    breaks so the full content is preserved.
    """
    if not paragraphs:
        return [f"(단락 {i + 1} 생성 실패)" for i in range(count)]

    if count == 1 and len(paragraphs) > 1:
        return ["\n\n".join(paragraphs)]

    result = list(paragraphs)
    while len(result) < count:
        result.append(f"(단락 {len(result) + 1} 생성 실패)")
    return result[:count]


def _escape_newlines_in_json(text: str) -> str:
    """
    Replace literal newlines inside JSON string values with \\n.

    Walks character by character tracking whether we're inside a
    quoted string. Literal \\n/\\r inside quotes become escaped.
    """
    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_string and i + 1 < len(text):
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            in_string = not in_string
        if in_string and ch == '\n':
            result.append('\\n')
        elif in_string and ch == '\r':
            result.append('\\r')
        else:
            result.append(ch)
        i += 1
    return ''.join(result)
