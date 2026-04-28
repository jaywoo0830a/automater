"""
automator/together_generator.py
---------------------------------
Together AI image generator.

Docs:
    https://docs.together.ai/docs/images-overview
    https://docs.together.ai/docs/error-codes
    https://docs.together.ai/docs/rate-limits

Endpoint: POST https://api.together.xyz/v1/images/generations

Error taxonomy (per docs.together.ai/docs/error-codes)
------------------------------------------------------
HTTP errors:
    400 misconfigured request           -- non-retryable (InvalidRequestError)
    401 invalid / missing API key       -- non-retryable (AuthenticationError)
    402 monthly spending limit reached  -- non-retryable (QuotaExceededError)
    403 context length exceeded         -- non-retryable (InvalidRequestError)
    404 invalid endpoint or model name  -- non-retryable (InvalidRequestError)
    422 unprocessable entity            -- non-retryable (InvalidRequestError)
    429 too many requests               -- RETRYABLE  (RateLimitError)
                                            error types:
                                              dynamic_request_limited
                                              dynamic_token_limited
    500 unknown server error            -- RETRYABLE  (ServerError)
    502 bad gateway                     -- RETRYABLE  (ServerError)
    503 high traffic / capacity strain  -- RETRYABLE  (ServerError)
    504 gateway timeout                 -- RETRYABLE  (ServerError)

Network/transport:
    TimeoutError, URLError              -- bounded retry (NetworkError)

Response shape:
    candidates missing / b64 missing    -- non-retryable (EmptyResponseError)

Rate-limit headers (logged for observability when present):
    x-ratelimit-limit / -remaining / -reset
    x-tokenlimit-limit / -remaining
    x-ratelimit-remaining-dynamic / x-tokenlimit-remaining-dynamic

Retry policy
------------
- 429 / 5xx / network: exponential backoff with jitter.
- Initial delay 5s, multiplier 2, jitter +/-20 percent.
- Max 5 attempts (initial + 4 retries) by default.
- Total worst-case wait approximately 75s + per-call timeouts.

Public surface
--------------
``generate()`` returns ``bytes`` on success and ``None`` on terminal failure
(after retries exhausted or on a non-retryable error). Layers in the image
processor are designed to skip on ``None`` and fall back to the base image,
so the caller never sees an exception. Internal control flow uses typed
``TogetherError`` subclasses for clarity at the WARNING / ERROR log level.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import time
import urllib.error
import urllib.request
from typing import override

from automator.ports import ImageGenerator


_log = logging.getLogger(__name__)

_ENDPOINT          = "https://api.together.xyz/v1/images/generations"
_DEFAULT_MODEL     = "black-forest-labs/FLUX.1-schnell"
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_STEPS     = 4       # schnell supports 1-4, dev/pro up to 50
_SIZE_STEP         = 8       # Together requires width/height multiples of 8
# Cloudflare in front of api.together.xyz rejects urllib's default UA.
_USER_AGENT        = "Mozilla/5.0 (compatible; automator/1.0)"

# Retry policy
_DEFAULT_MAX_ATTEMPTS         = 5      # 1 initial + 4 retries
_DEFAULT_INITIAL_DELAY_SEC    = 5.0
_DEFAULT_BACKOFF_MULTIPLIER   = 2.0
_DEFAULT_JITTER_RATIO         = 0.2    # +/-20%
_RETRYABLE_STATUS_CODES       = frozenset({429, 500, 502, 503, 504})

# Headers we surface in logs (case-insensitive lookup applied below)
_RATE_LIMIT_HEADER_KEYS = (
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-ratelimit-limit-dynamic",
    "x-ratelimit-remaining-dynamic",
    "x-tokenlimit-limit",
    "x-tokenlimit-remaining",
    "x-tokenlimit-limit-dynamic",
    "x-tokenlimit-remaining-dynamic",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TogetherError(Exception):
    """Base exception for all Together API failures."""


class TogetherInvalidRequestError(TogetherError):
    """400 / 403 / 404 / 422 -- bad request, model, or endpoint."""


class TogetherAuthenticationError(TogetherError):
    """401 -- missing or invalid API key."""


class TogetherQuotaExceededError(TogetherError):
    """402 -- monthly spending limit reached."""


class TogetherRateLimitError(TogetherError):
    """429 -- too many requests, dynamic rate exceeded. Retryable."""


class TogetherServerError(TogetherError):
    """500 / 502 / 503 / 504 -- transient upstream failure. Retryable."""


class TogetherNetworkError(TogetherError):
    """Connection / timeout failure. Retryable (bounded)."""


class TogetherEmptyResponseError(TogetherError):
    """200 OK but response shape is unusable. Non-retryable."""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class TogetherImageGenerator(ImageGenerator):
    """Together AI image generator via /v1/images/generations.

    Args:
        api_key:         API key. Defaults to $TOGETHER_API_KEY.
        model:           Default model. Defaults to $TOGETHER_MODEL, then FLUX.1-schnell.
        timeout_s:       HTTP timeout in seconds.
        steps:           Default inference steps.
        max_attempts:    Total attempts (initial + retries) for retryable errors.
        initial_delay_s: First retry sleep (exponential backoff base).
    """

    def __init__(
        self,
        api_key:         str   = "",
        model:           str   = "",
        *,
        timeout_s:       float = _DEFAULT_TIMEOUT_S,
        steps:           int   = _DEFAULT_STEPS,
        max_attempts:    int   = _DEFAULT_MAX_ATTEMPTS,
        initial_delay_s: float = _DEFAULT_INITIAL_DELAY_SEC,
    ) -> None:
        self._api_key         = api_key or os.getenv("TOGETHER_API_KEY", "")
        self._model           = model or os.getenv("TOGETHER_MODEL", "") or _DEFAULT_MODEL
        self._timeout_s       = timeout_s
        self._steps           = steps
        self._max_attempts    = max(1, int(max_attempts))
        self._initial_delay_s = max(0.0, float(initial_delay_s))

    @override
    def generate(
        self,
        prompt: str,
        *,
        width:  int | None = None,
        height: int | None = None,
        seed:   int | None = None,
        model:  str        = "",
    ) -> bytes | None:
        if not prompt or not prompt.strip():
            _log.warning("Together: empty prompt")
            return None
        if not self._api_key:
            _log.warning("Together: TOGETHER_API_KEY not set")
            return None

        body: dict = {
            "model":           model or self._model,
            "prompt":          prompt.strip(),
            "steps":           self._steps,
            "n":               1,
            "response_format": "base64",
        }
        if width  is not None: body["width"]  = _snap(width,  _SIZE_STEP)
        if height is not None: body["height"] = _snap(height, _SIZE_STEP)
        if seed   is not None: body["seed"]   = seed

        try:
            return self._post_with_retries(body)
        except TogetherError as exc:
            # Terminal failure (non-retryable, or retries exhausted). The image
            # processor expects None on failure and falls back to the base.
            _log.error(
                "Together generation failed (%s): %s",
                type(exc).__name__, exc,
            )
            return None

    # -----------------------------------------------------------------------
    # Retry loop
    # -----------------------------------------------------------------------

    def _post_with_retries(self, body: dict) -> bytes:
        """Call ``_post_once`` with exponential backoff on retryable errors."""
        last_exc: TogetherError | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._post_once(body)
            except (TogetherRateLimitError, TogetherServerError, TogetherNetworkError) as exc:
                last_exc = exc
                if attempt >= self._max_attempts:
                    raise
                delay = self._backoff_delay(attempt)
                _log.warning(
                    "Together %s on attempt %d/%d -- retrying in %.1fs: %s",
                    type(exc).__name__, attempt, self._max_attempts, delay, exc,
                )
                time.sleep(delay)
            except TogetherError:
                # Non-retryable: invalid request / auth / quota / shape.
                raise
        # Unreachable: loop either returns or raises. Defensive guard.
        if last_exc:
            raise last_exc
        raise TogetherError("Together: no attempts executed")

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with bounded jitter."""
        base = self._initial_delay_s * (_DEFAULT_BACKOFF_MULTIPLIER ** (attempt - 1))
        if _DEFAULT_JITTER_RATIO <= 0:
            return base
        lo = 1.0 - _DEFAULT_JITTER_RATIO
        hi = 1.0 + _DEFAULT_JITTER_RATIO
        return base * random.uniform(lo, hi)

    # -----------------------------------------------------------------------
    # Single HTTP attempt
    # -----------------------------------------------------------------------

    def _post_once(self, body: dict) -> bytes:
        """One HTTP call. Returns image bytes or raises a typed TogetherError."""
        req = urllib.request.Request(
            _ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
                "User-Agent":    _USER_AGENT,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                _maybe_log_rate_limits(getattr(resp, "headers", None))
                payload_bytes = resp.read()
        except urllib.error.HTTPError as exc:
            raise _classify_http_error(exc) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TogetherNetworkError(
                f"network failure ({type(exc).__name__}): {exc}"
            ) from exc

        try:
            payload = json.loads(payload_bytes)
        except json.JSONDecodeError as exc:
            raise TogetherEmptyResponseError(
                f"invalid JSON in response: {exc}"
            ) from exc

        try:
            b64 = payload["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TogetherEmptyResponseError(
                f"unexpected response shape: missing data[0].b64_json ({exc})"
            ) from exc

        try:
            return base64.b64decode(b64)
        except (ValueError, TypeError) as exc:
            raise TogetherEmptyResponseError(
                f"invalid base64 payload: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(value: int, step: int) -> int:
    """Round ``value`` down to a multiple of ``step``, clamped to [step, ∞)."""
    return max(step, (value // step) * step)


def _classify_http_error(exc: urllib.error.HTTPError) -> TogetherError:
    """Map a ``urllib`` ``HTTPError`` to a typed ``TogetherError`` subclass.

    Reads up to 1KiB of the response body for a human-readable error message
    (Together returns JSON shapes like ``{"error": {"message": "...", "type": "..."}}``).
    """
    code = exc.code
    body_snippet = ""
    try:
        raw = exc.read()
    except Exception:
        raw = b""
    if raw:
        body_snippet = raw[:1024].decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body_snippet)
            err = parsed.get("error") if isinstance(parsed, dict) else None
            if isinstance(err, dict) and "message" in err:
                msg_parts = [str(err.get("message", "")).strip()]
                err_type = err.get("type")
                if err_type:
                    msg_parts.append(f"type={err_type}")
                body_snippet = " | ".join(p for p in msg_parts if p)
            elif isinstance(parsed, dict) and "message" in parsed:
                body_snippet = str(parsed["message"]).strip()
        except (json.JSONDecodeError, ValueError):
            pass

    _maybe_log_rate_limits(getattr(exc, "headers", None))

    if code == 400:
        return TogetherInvalidRequestError(f"HTTP 400 misconfigured request: {body_snippet}")
    if code == 401:
        return TogetherAuthenticationError(f"HTTP 401 invalid API key: {body_snippet}")
    if code == 402:
        return TogetherQuotaExceededError(
            f"HTTP 402 monthly spending limit reached: {body_snippet}"
        )
    if code == 403:
        return TogetherInvalidRequestError(
            f"HTTP 403 context length / forbidden: {body_snippet}"
        )
    if code == 404:
        return TogetherInvalidRequestError(f"HTTP 404 endpoint or model not found: {body_snippet}")
    if code == 422:
        return TogetherInvalidRequestError(f"HTTP 422 unprocessable entity: {body_snippet}")
    if code == 429:
        return TogetherRateLimitError(
            f"HTTP 429 rate limit exceeded -- slow down: {body_snippet}"
        )
    if code in _RETRYABLE_STATUS_CODES:
        return TogetherServerError(f"HTTP {code} server error: {body_snippet}")
    return TogetherError(f"HTTP {code}: {body_snippet}")


def _maybe_log_rate_limits(headers) -> None:
    """Log rate-limit headers when present at DEBUG, or WARNING if remaining is 0."""
    if headers is None:
        return
    # urllib3/HTTPMessage supports case-insensitive lookup; normalize to dict.
    try:
        items = {k.lower(): v for k, v in headers.items()}
    except Exception:
        return

    surfaced = {k: items[k] for k in _RATE_LIMIT_HEADER_KEYS if k in items}
    if not surfaced:
        return

    # Soft warning when any "remaining" is at or below zero.
    low = any(
        _safe_float(v) is not None and _safe_float(v) <= 0
        for k, v in surfaced.items()
        if "remaining" in k
    )
    if low:
        _log.warning("Together rate-limit headers: %s", surfaced)
    else:
        _log.debug("Together rate-limit headers: %s", surfaced)


def _safe_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
