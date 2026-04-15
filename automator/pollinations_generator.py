"""
automator/pollinations_generator.py
-------------------------------------
PollinationsImageGenerator — free, no-auth AI image generator.

Endpoint: https://image.pollinations.ai/prompt/{prompt}?...

Every call hits the API; no caching. Network/HTTP failures return None so
the caller can fall back to the base image without failing the whole post.
"""

from __future__ import annotations

import logging
import urllib.error
import urllib.parse
import urllib.request

from automator.ports import ImageGenerator


_log = logging.getLogger(__name__)

_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
_DEFAULT_TIMEOUT_S = 30.0


class PollinationsImageGenerator(ImageGenerator):
    """
    Args:
        timeout_s: HTTP request timeout in seconds.
        nologo:    If True, request image without Pollinations watermark.
    """

    def __init__(self, *, timeout_s: float = _DEFAULT_TIMEOUT_S, nologo: bool = True) -> None:
        self._timeout_s = timeout_s
        self._nologo = nologo

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
            _log.warning("Pollinations: empty prompt, skipping")
            return None

        url = self._build_url(prompt.strip(), width, height, seed, model)

        try:
            with urllib.request.urlopen(url, timeout=self._timeout_s) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _log.warning("Pollinations generation failed (%s): %s", type(e).__name__, e)
            return None

    def _build_url(
        self,
        prompt: str,
        width:  int | None,
        height: int | None,
        seed:   int | None,
        model:  str,
    ) -> str:
        base = _POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt, safe=""))

        params: dict[str, str] = {}
        if width:  params["width"]  = str(width)
        if height: params["height"] = str(height)
        if seed is not None: params["seed"] = str(seed)
        if model:  params["model"]  = model
        if self._nologo: params["nologo"] = "true"

        if params:
            return f"{base}?{urllib.parse.urlencode(params)}"
        return base
