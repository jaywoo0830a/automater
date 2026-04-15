"""
tests/unit/automator/test_pollinations_generator.py
------------------------------------------------------
Pollinations image generator — URL building and failure handling.

No real network calls — HTTP is stubbed.
"""

import io
import urllib.error
from unittest.mock import patch

import pytest
from PIL import Image

from automator.pollinations_generator import PollinationsImageGenerator


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (123, 45, 67)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeResp:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
    def read(self) -> bytes:
        return self._payload
    def __enter__(self): return self
    def __exit__(self, *a): return False


class TestURLBuilding:
    def test_minimal_url(self):
        gen = PollinationsImageGenerator(nologo=False)
        url = gen._build_url("a cat", None, None, None, "")
        assert url == "https://image.pollinations.ai/prompt/a%20cat"

    def test_with_all_params(self):
        gen = PollinationsImageGenerator(nologo=True)
        url = gen._build_url("hi", 512, 256, 42, "flux")
        assert url.startswith("https://image.pollinations.ai/prompt/hi?")
        assert "width=512" in url
        assert "height=256" in url
        assert "seed=42" in url
        assert "model=flux" in url
        assert "nologo=true" in url

    def test_prompt_special_chars_encoded(self):
        gen = PollinationsImageGenerator(nologo=False)
        url = gen._build_url("a/b?c&d", None, None, None, "")
        assert "/a%2Fb%3Fc%26d" in url

    def test_seed_zero_is_included(self):
        """seed=0 is a valid seed; must not be dropped by truthiness."""
        gen = PollinationsImageGenerator(nologo=False)
        url = gen._build_url("x", None, None, 0, "")
        assert "seed=0" in url


class TestGenerate:
    def test_returns_bytes_on_success(self):
        gen = PollinationsImageGenerator()
        payload = _png_bytes()
        with patch("urllib.request.urlopen", return_value=_FakeResp(payload)):
            result = gen.generate("a cat")
        assert result == payload

    def test_returns_none_on_url_error(self):
        gen = PollinationsImageGenerator()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            assert gen.generate("x") is None

    def test_returns_none_on_timeout(self):
        gen = PollinationsImageGenerator()
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            assert gen.generate("x") is None

    def test_empty_prompt_returns_none_no_http(self):
        gen = PollinationsImageGenerator()
        with patch("urllib.request.urlopen") as m:
            assert gen.generate("   ") is None
            m.assert_not_called()
