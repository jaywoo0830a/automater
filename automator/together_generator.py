"""
automator/together_generator.py
---------------------------------
TogetherImageGenerator — Together AI image generation.

Endpoint: POST https://api.together.xyz/v1/images/generations
Auth:     Bearer token (TOGETHER_API_KEY env var by default)

Default model: black-forest-labs/FLUX.1-schnell-Free (free tier, rate-limited).
Paid:          black-forest-labs/FLUX.1-schnell  (~$0.0027/img)

Network / HTTP errors return None so the caller falls back to the base image.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request

from automator.ports import ImageGenerator


_log = logging.getLogger(__name__)

_ENDPOINT = "https://api.together.xyz/v1/images/generations"
_DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell-Free"
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_STEPS = 4  # FLUX.1-schnell only supports 1-4 steps


class TogetherImageGenerator(ImageGenerator):
    """
    Args:
        api_key:   Together AI API key. Falls back to TOGETHER_API_KEY env var.
        model:     Default model ID. Can be overridden per-call.
        timeout_s: HTTP request timeout in seconds.
        steps:     Inference steps (FLUX schnell: 1-4).
    """

    def __init__(
        self,
        api_key:   str   = "",
        model:     str   = _DEFAULT_MODEL,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        steps:     int   = _DEFAULT_STEPS,
    ) -> None:
        self._api_key   = api_key or os.getenv("TOGETHER_API_KEY", "")
        self._model     = model
        self._timeout_s = timeout_s
        self._steps     = steps

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
            _log.warning("Together: empty prompt, skipping")
            return None
        if not self._api_key:
            _log.warning("Together: TOGETHER_API_KEY not set, skipping")
            return None

        payload: dict = {
            "model":           model or self._model,
            "prompt":          prompt.strip(),
            "steps":           self._steps,
            "n":               1,
            "response_format": "b64_json",
        }
        if width:  payload["width"]  = _snap_to_multiple(width, 32)
        if height: payload["height"] = _snap_to_multiple(height, 32)
        if seed is not None: payload["seed"] = seed

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type":  "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            _log.warning("Together HTTP %d: %s", e.code, e.read()[:200])
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _log.warning("Together request failed (%s): %s", type(e).__name__, e)
            return None

        try:
            data = json.loads(raw)
            b64 = data["data"][0]["b64_json"]
            return base64.b64decode(b64)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            _log.warning("Together: unexpected response shape (%s)", e)
            return None


def _snap_to_multiple(value: int, step: int) -> int:
    """Round down to the nearest multiple of ``step`` (FLUX size constraint)."""
    snapped = (value // step) * step
    return max(step, snapped)
