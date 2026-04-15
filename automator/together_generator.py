"""
automator/together_generator.py
---------------------------------
Together AI image generator.

Docs:     https://docs.together.ai/docs/images-overview
Endpoint: POST https://api.together.xyz/v1/images/generations

Returns bytes on success, None on any failure so the caller can fall back to
the base image without aborting the whole post.
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

_ENDPOINT          = "https://api.together.xyz/v1/images/generations"
_DEFAULT_MODEL     = "black-forest-labs/FLUX.1-schnell"
_DEFAULT_TIMEOUT_S = 60.0
_DEFAULT_STEPS     = 4       # schnell supports 1-4, dev/pro up to 50
_SIZE_STEP         = 8       # Together requires width/height multiples of 8
# Cloudflare in front of api.together.xyz rejects urllib's default UA.
_USER_AGENT        = "Mozilla/5.0 (compatible; automator/1.0)"


class TogetherImageGenerator(ImageGenerator):
    """Together AI image generator via /v1/images/generations.

    Args:
        api_key:   API key. Defaults to $TOGETHER_API_KEY.
        model:     Default model. Defaults to $TOGETHER_MODEL, then FLUX.1-schnell.
        timeout_s: HTTP timeout in seconds.
        steps:     Default inference steps.
    """

    def __init__(
        self,
        api_key:   str   = "",
        model:     str   = "",
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        steps:     int   = _DEFAULT_STEPS,
    ) -> None:
        self._api_key   = api_key or os.getenv("TOGETHER_API_KEY", "")
        self._model     = model or os.getenv("TOGETHER_MODEL", "") or _DEFAULT_MODEL
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

        return self._post(body)

    def _post(self, body: dict) -> bytes | None:
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
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            _log.warning("Together HTTP %d: %s", e.code, e.read()[:300])
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _log.warning("Together request failed (%s): %s", type(e).__name__, e)
            return None
        except json.JSONDecodeError as e:
            _log.warning("Together: invalid JSON response: %s", e)
            return None

        try:
            return base64.b64decode(payload["data"][0]["b64_json"])
        except (KeyError, IndexError, TypeError, ValueError) as e:
            _log.warning("Together: unexpected response shape (%s)", e)
            return None


def _snap(value: int, step: int) -> int:
    """Round ``value`` down to a multiple of ``step``, clamped to [step, ∞)."""
    return max(step, (value // step) * step)
