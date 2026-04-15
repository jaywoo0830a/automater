"""
tests/unit/automator/test_together_generator.py
--------------------------------------------------
Together AI image generator — request building and failure handling.

No real network calls — HTTP is stubbed.
"""

import base64
import io
import json
import urllib.error
from unittest.mock import patch

import pytest
from PIL import Image

from automator.together_generator import TogetherImageGenerator


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (123, 45, 67)).save(buf, format="PNG")
    return buf.getvalue()


def _ok_response(payload_bytes: bytes) -> "_FakeResp":
    body = json.dumps({
        "data": [{"b64_json": base64.b64encode(payload_bytes).decode()}]
    }).encode()
    return _FakeResp(body)


class _FakeResp:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
    def read(self) -> bytes:
        return self._payload
    def __enter__(self): return self
    def __exit__(self, *a): return False


class TestRequestBuilding:
    def test_missing_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
        gen = TogetherImageGenerator()
        with patch("urllib.request.urlopen") as m:
            assert gen.generate("x") is None
            m.assert_not_called()

    def test_empty_prompt_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        with patch("urllib.request.urlopen") as m:
            assert gen.generate("   ") is None
            m.assert_not_called()

    def test_sends_bearer_token(self):
        gen = TogetherImageGenerator(api_key="sk-test")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            captured["body"] = json.loads(req.data)
            captured["url"] = req.full_url
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = gen.generate("a cat")

        assert result == _png_bytes()
        assert captured["url"] == "https://api.together.xyz/v1/images/generations"
        # urllib normalizes header names (Title-Case)
        auth = captured["headers"].get("Authorization")
        assert auth == "Bearer sk-test"
        assert captured["body"]["prompt"] == "a cat"
        assert captured["body"]["model"] == "black-forest-labs/FLUX.1-schnell-Free"
        assert captured["body"]["response_format"] == "b64_json"
        assert captured["body"]["steps"] == 4

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("TOGETHER_API_KEY", "env-key")
        gen = TogetherImageGenerator()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x")

        assert captured["headers"]["Authorization"] == "Bearer env-key"

    def test_size_snapped_to_multiple_of_32(self):
        gen = TogetherImageGenerator(api_key="k")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x", width=1000, height=777)

        assert captured["body"]["width"] == 992   # floor(1000/32)*32
        assert captured["body"]["height"] == 768  # floor(777/32)*32

    def test_seed_zero_is_included(self):
        gen = TogetherImageGenerator(api_key="k")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x", seed=0)

        assert captured["body"]["seed"] == 0

    def test_per_call_model_overrides_default(self):
        gen = TogetherImageGenerator(api_key="k")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x", model="black-forest-labs/FLUX.1-schnell")

        assert captured["body"]["model"] == "black-forest-labs/FLUX.1-schnell"


class TestFailureHandling:
    def test_http_error_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        err = urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b"rate limit"))
        with patch("urllib.request.urlopen", side_effect=err):
            assert gen.generate("x") is None

    def test_url_error_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            assert gen.generate("x") is None

    def test_timeout_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            assert gen.generate("x") is None

    def test_malformed_response_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"bogus": 1}')):
            assert gen.generate("x") is None

    def test_invalid_json_returns_none(self):
        gen = TogetherImageGenerator(api_key="k")
        with patch("urllib.request.urlopen", return_value=_FakeResp(b"not json")):
            assert gen.generate("x") is None
