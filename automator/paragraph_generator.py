"""
automator/paragraph_generator.py
----------------------------------
Paragraph generation via Gemini API.

    generate_paragraph(prompt)  -> str

ENV=production  -> calls Gemini API
ENV=dev | test  -> returns stub paragraphs (no dependencies)

Gemini API error taxonomy (google.dev/gemini-api/docs)
------------------------------------------------------
HTTP errors (raised by SDK as exceptions):
    400 INVALID_ARGUMENT       — malformed request / bad params
    400 FAILED_PRECONDITION    — billing required (free tier region)
    403 PERMISSION_DENIED      — bad API key / leaked key
    404 NOT_FOUND              — invalid model name
    429 RESOURCE_EXHAUSTED     — rate limit (RPM / TPM / RPD)
    500 INTERNAL               — Google server error
    503 UNAVAILABLE            — service overloaded
    504 DEADLINE_EXCEEDED      — response took too long

Response-level failures (response returned but unusable):
    prompt blocked             — promptFeedback.blockReason set, no candidates
    finish_reason=SAFETY       — output blocked by safety filter
    finish_reason=RECITATION   — output blocked by copyright filter
    finish_reason=BLOCKLIST    — term blocklist match
    finish_reason=PROHIBITED_CONTENT — explicitly prohibited
    finish_reason=SPII         — sensitive PII detected
    finish_reason=MAX_TOKENS   — truncated (may still be usable)
    finish_reason=MALFORMED_FUNCTION_CALL — bad function call syntax
    empty text                 — candidates exist but text is empty
"""

from __future__ import annotations

import logging
import os

from automator.config import is_production

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GeminiError(Exception):
    """Base exception for all Gemini API failures."""


class RateLimitError(GeminiError):
    """429 RESOURCE_EXHAUSTED — rate limit exceeded (RPM/TPM/RPD)."""


class SafetyBlockError(GeminiError):
    """Response blocked by safety / recitation / blocklist / prohibited content / SPII filter."""


class EmptyResponseError(GeminiError):
    """API returned a response but text is empty or candidates are missing."""


class PromptBlockedError(GeminiError):
    """Prompt itself was blocked before generation (promptFeedback.blockReason)."""


class ServerError(GeminiError):
    """500 INTERNAL / 503 UNAVAILABLE / 504 DEADLINE_EXCEEDED — transient server failure."""


class AuthenticationError(GeminiError):
    """403 PERMISSION_DENIED — invalid or leaked API key."""


class InvalidRequestError(GeminiError):
    """400 INVALID_ARGUMENT / FAILED_PRECONDITION / 404 NOT_FOUND — bad request."""


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

# finish_reason → 차단으로 간주하는 값들
_BLOCKED_REASONS = frozenset({
    "SAFETY", "RECITATION", "BLOCKLIST",
    "PROHIBITED_CONTENT", "SPII",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_paragraph(
    prompt: str,
    api_key: str = "",
    model: str = "",
) -> str:
    """
    Send ``prompt`` to Gemini and return the response text.

    프롬프트는 호출자가 완전히 제어한다. 이 함수는 시스템 프롬프트나
    출력 형식 지시를 일체 추가하지 않고 ``prompt``를 그대로 전달한다.

    ENV=production  -> calls Gemini API; errors propagate.
    ENV=dev | test  -> returns a stub paragraph, no API call.

    Raises:
        RateLimitError:      429 rate limit.
        SafetyBlockError:    Content blocked by safety/recitation/blocklist.
        PromptBlockedError:  Prompt itself was blocked.
        EmptyResponseError:  API returned empty text.
        ServerError:         500/503/504 transient failure.
        AuthenticationError: 403 bad API key.
        InvalidRequestError: 400/404 bad request.
    """
    if not is_production():
        return _stub_generate(1)[0]

    resolved_key = api_key or os.getenv("GEMINI_API_KEY", "")
    resolved_model = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL)

    if not resolved_key:
        raise AuthenticationError(
            "Gemini API key is required in production. "
            "Set GEMINI_API_KEY in .env or pass api_key= explicitly."
        )

    return _call_api(prompt, resolved_key, resolved_model)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _stub_generate(count: int) -> list[str]:
    """Return ``count`` stub paragraphs (UDHR Korean). Cycles if needed."""
    return [
        _STUB_PARAGRAPHS[i % len(_STUB_PARAGRAPHS)]
        for i in range(count)
    ]


def _classify_http_error(exc: Exception) -> GeminiError:
    """Classify an SDK exception into the appropriate GeminiError subclass."""
    msg = str(exc)

    # 429 Rate limit
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return RateLimitError(f"Rate limit exceeded: {msg}")

    # 403 Permission
    if "403" in msg or "PERMISSION_DENIED" in msg:
        return AuthenticationError(f"API key invalid or revoked: {msg}")

    # 500 / 503 / 504 Server errors
    if any(code in msg for code in ("500", "503", "504", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
        return ServerError(f"Gemini server error: {msg}")

    # 400 / 404 Client errors
    if any(code in msg for code in ("400", "404", "INVALID_ARGUMENT", "FAILED_PRECONDITION", "NOT_FOUND")):
        return InvalidRequestError(f"Bad request: {msg}")

    # Unknown — wrap in base class
    return GeminiError(f"Gemini API error: {msg}")


def _call_api(prompt: str, api_key: str, model: str) -> str:
    """Send ``prompt`` to Gemini as-is and return the validated response text.

    No system instruction, no output format wrapping — the caller owns
    the entire prompt content.

    Raises the appropriate GeminiError subclass on any failure.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # ── HTTP 요청 ──
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=65536,
            ),
        )
    except Exception as exc:
        raise _classify_http_error(exc) from exc

    # ── 프롬프트 차단 확인 ──
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback:
        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason:
            raise PromptBlockedError(
                f"Prompt blocked by Gemini. "
                f"block_reason: {block_reason}, "
                f"prompt_feedback: {prompt_feedback}"
            )

    # ── candidates 존재 확인 ──
    candidates = getattr(response, "candidates", None)
    if not candidates:
        raise EmptyResponseError(
            f"No candidates in response. "
            f"prompt_feedback: {prompt_feedback}"
        )

    # ── finish_reason 확인 ──
    candidate = candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    reason_str = str(finish_reason).upper() if finish_reason else ""

    # 차단된 finish_reason
    for blocked in _BLOCKED_REASONS:
        if blocked in reason_str:
            safety_ratings = getattr(candidate, "safety_ratings", None)
            raise SafetyBlockError(
                f"Response blocked. "
                f"finish_reason: {finish_reason}, "
                f"safety_ratings: {safety_ratings}"
            )

    # MAX_TOKENS — 잘렸지만 텍스트가 있으면 경고만 하고 진행
    if "MAX_TOKENS" in reason_str:
        logger.warning(
            "[gemini] 응답이 max_tokens에 의해 잘림 — 잘린 텍스트 그대로 사용"
        )

    # ── 텍스트 추출 ──
    try:
        text = response.text or ""
    except Exception:
        # response.text 접근 자체가 실패하는 경우 (차단 시 SDK가 raise)
        text = ""

    if not text.strip():
        raise EmptyResponseError(
            f"Empty response text. "
            f"finish_reason: {finish_reason}, "
            f"candidates: {len(candidates)}"
        )

    return text
