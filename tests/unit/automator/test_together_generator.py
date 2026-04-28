"""
tests/unit/automator/test_together_generator.py
--------------------------------------------------
Together AI image generator — request building, error taxonomy, and retries.

No real network calls — HTTP is stubbed. ``max_attempts=1`` is used in
failure-only tests so a single failure terminates immediately; retry tests
explicitly drive the exponential backoff via mocked ``time.sleep``.
"""

import base64
import io
import json
import urllib.error
from unittest.mock import patch

import pytest
from PIL import Image

from automator.together_generator import (
    TogetherAuthenticationError,
    TogetherEmptyResponseError,
    TogetherImageGenerator,
    TogetherInvalidRequestError,
    TogetherNetworkError,
    TogetherQuotaExceededError,
    TogetherRateLimitError,
    TogetherServerError,
)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (123, 45, 67)).save(buf, format="PNG")
    return buf.getvalue()


def _ok_response(payload_bytes: bytes, headers: dict | None = None) -> "_FakeResp":
    body = json.dumps({
        "data": [{"b64_json": base64.b64encode(payload_bytes).decode()}]
    }).encode()
    return _FakeResp(body, headers=headers)


def _http_error(status: int, body: bytes = b"", headers: dict | None = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.together.xyz/v1/images/generations",
        code=status,
        msg="err",
        hdrs=headers or {},
        fp=io.BytesIO(body),
    )


class _FakeResp:
    def __init__(self, payload: bytes, headers: dict | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}
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

    def test_sends_bearer_token(self, monkeypatch):
        monkeypatch.delenv("TOGETHER_MODEL", raising=False)
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
        assert captured["headers"]["Authorization"] == "Bearer sk-test"
        assert captured["headers"]["User-agent"].startswith("Mozilla/")
        assert captured["body"]["prompt"] == "a cat"
        assert captured["body"]["model"] == "black-forest-labs/FLUX.1-schnell"
        assert captured["body"]["response_format"] == "base64"
        assert captured["body"]["steps"] == 4
        assert captured["body"]["n"] == 1

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("TOGETHER_API_KEY", "env-key")
        monkeypatch.delenv("TOGETHER_MODEL", raising=False)
        gen = TogetherImageGenerator()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x")

        assert captured["headers"]["Authorization"] == "Bearer env-key"

    def test_model_env_var(self, monkeypatch):
        monkeypatch.setenv("TOGETHER_MODEL", "black-forest-labs/FLUX.1-dev")
        gen = TogetherImageGenerator(api_key="k")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x")

        assert captured["body"]["model"] == "black-forest-labs/FLUX.1-dev"

    def test_ctor_model_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TOGETHER_MODEL", "env-model")
        gen = TogetherImageGenerator(api_key="k", model="ctor-model")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x")

        assert captured["body"]["model"] == "ctor-model"

    def test_size_snapped_to_multiple_of_16(self):
        # Together API requires multiples of 16 (older docs say 8, but the
        # service rejects 8-aligned values with "width must be a multiple of 16").
        gen = TogetherImageGenerator(api_key="k")
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data)
            return _ok_response(_png_bytes())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            gen.generate("x", width=1000, height=777)

        assert captured["body"]["width"] == 992   # floor(1000/16)*16
        assert captured["body"]["height"] == 768  # floor(777/16)*16

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
    """Each failure mode terminates as None at the public surface.

    ``max_attempts=1`` is used so retryable errors fail immediately rather
    than triggering the backoff loop. Retry behavior is covered separately
    below.
    """

    def test_http_error_returns_none(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=_http_error(429, b"rate limit")):
            assert gen.generate("x") is None

    def test_url_error_returns_none(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            assert gen.generate("x") is None

    def test_timeout_returns_none(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            assert gen.generate("x") is None

    def test_malformed_response_returns_none(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"bogus": 1}')):
            assert gen.generate("x") is None

    def test_invalid_json_returns_none(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", return_value=_FakeResp(b"not json")):
            assert gen.generate("x") is None


# ---------------------------------------------------------------------------
# Error classification — internal exceptions
# ---------------------------------------------------------------------------

class TestErrorClassification:
    """Each HTTP code maps to a specific TogetherError subclass.

    These tests bypass the public ``generate()`` (which converts to None)
    and exercise ``_post_once`` directly so the typed exception is visible.
    """

    @pytest.mark.parametrize("status, exc_cls", [
        (400, TogetherInvalidRequestError),
        (401, TogetherAuthenticationError),
        (402, TogetherQuotaExceededError),
        (403, TogetherInvalidRequestError),
        (404, TogetherInvalidRequestError),
        (422, TogetherInvalidRequestError),
        (429, TogetherRateLimitError),
        (500, TogetherServerError),
        (502, TogetherServerError),
        (503, TogetherServerError),
        (504, TogetherServerError),
    ])
    def test_status_maps_to_exception(self, status, exc_cls):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=_http_error(status, b"{}")):
            with pytest.raises(exc_cls):
                gen._post_once({"model": "m", "prompt": "x"})

    def test_network_failure_raises_network_error(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with pytest.raises(TogetherNetworkError):
                gen._post_once({"model": "m", "prompt": "x"})

    def test_timeout_raises_network_error(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            with pytest.raises(TogetherNetworkError):
                gen._post_once({"model": "m", "prompt": "x"})

    def test_bad_shape_raises_empty_response(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"foo": 1}')):
            with pytest.raises(TogetherEmptyResponseError):
                gen._post_once({"model": "m", "prompt": "x"})

    def test_error_body_message_extracted(self):
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        body = json.dumps({
            "error": {"message": "bad input", "type": "invalid_request_error"}
        }).encode()
        with patch("urllib.request.urlopen", side_effect=_http_error(400, body)):
            with pytest.raises(TogetherInvalidRequestError, match="bad input"):
                gen._post_once({"model": "m", "prompt": "x"})


# ---------------------------------------------------------------------------
# Retry behavior — exponential backoff, retryable vs non-retryable
# ---------------------------------------------------------------------------

class TestRetryBehavior:

    def _gen(self, max_attempts=4):
        return TogetherImageGenerator(
            api_key="k", max_attempts=max_attempts, initial_delay_s=0.0,
        )

    def test_429_then_success_returns_image(self):
        # 429 on first call → retry → success on second call.
        responses = [
            _http_error(429, b'{"error":{"message":"slow down","type":"dynamic_request_limited"}}'),
            _ok_response(_png_bytes()),
        ]

        def side_effect(req, timeout):
            r = responses.pop(0)
            if isinstance(r, urllib.error.HTTPError):
                raise r
            return r

        with patch("urllib.request.urlopen", side_effect=side_effect), \
             patch("automator.together_generator.time.sleep"):
            assert self._gen().generate("x") == _png_bytes()
        assert responses == []  # both consumed

    def test_503_then_success_returns_image(self):
        responses = [_http_error(503, b"overloaded"), _ok_response(_png_bytes())]
        def side_effect(req, timeout):
            r = responses.pop(0)
            if isinstance(r, urllib.error.HTTPError):
                raise r
            return r

        with patch("urllib.request.urlopen", side_effect=side_effect), \
             patch("automator.together_generator.time.sleep"):
            assert self._gen().generate("x") == _png_bytes()

    def test_timeout_then_success_returns_image(self):
        ok = _ok_response(_png_bytes())
        responses = [TimeoutError(), ok]
        def side_effect(req, timeout):
            r = responses.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r

        with patch("urllib.request.urlopen", side_effect=side_effect), \
             patch("automator.together_generator.time.sleep"):
            assert self._gen().generate("x") == _png_bytes()

    def test_429_exhausts_attempts_returns_none(self):
        # All 4 attempts fail with 429 — final result is None.
        with patch("urllib.request.urlopen", side_effect=_http_error(429, b"")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=4).generate("x") is None
        assert m.call_count == 4

    def test_500_exhausts_attempts_returns_none(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(500, b"")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=3).generate("x") is None
        assert m.call_count == 3

    def test_400_no_retry(self):
        # Non-retryable: only one call should be made.
        with patch("urllib.request.urlopen", side_effect=_http_error(400, b"bad")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=5).generate("x") is None
        assert m.call_count == 1

    def test_401_no_retry(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(401, b"")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=5).generate("x") is None
        assert m.call_count == 1

    def test_402_no_retry(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(402, b"")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=5).generate("x") is None
        assert m.call_count == 1

    def test_404_no_retry(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(404, b"")) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=5).generate("x") is None
        assert m.call_count == 1

    def test_bad_shape_no_retry(self):
        with patch("urllib.request.urlopen", return_value=_FakeResp(b'{"a":1}')) as m, \
             patch("automator.together_generator.time.sleep"):
            assert self._gen(max_attempts=5).generate("x") is None
        assert m.call_count == 1

    def test_backoff_increases(self):
        # Three consecutive failures → two sleeps with growing delays.
        delays = []

        def fake_sleep(d):
            delays.append(d)

        with patch("urllib.request.urlopen", side_effect=_http_error(429, b"")), \
             patch("automator.together_generator.time.sleep", side_effect=fake_sleep):
            gen = TogetherImageGenerator(
                api_key="k", max_attempts=3, initial_delay_s=1.0,
            )
            gen.generate("x")

        assert len(delays) == 2
        # With +/-20% jitter, second delay is roughly 2x first delay.
        # Use a generous lower bound to avoid flake.
        assert delays[1] > delays[0]


# ---------------------------------------------------------------------------
# Rate-limit headers logged for observability
# ---------------------------------------------------------------------------

class TestRateLimitHeaders:

    def test_headers_logged_at_debug_when_remaining_positive(self, caplog):
        import logging
        caplog.set_level(logging.DEBUG, logger="automator.together_generator")
        headers = {
            "x-ratelimit-limit": "10",
            "x-ratelimit-remaining": "7",
            "x-ratelimit-reset": "1.5",
        }
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen",
                   return_value=_ok_response(_png_bytes(), headers=headers)):
            gen.generate("x")
        assert any("x-ratelimit-remaining" in r.message for r in caplog.records)

    def test_remaining_zero_logged_at_warning(self, caplog):
        import logging
        caplog.set_level(logging.WARNING, logger="automator.together_generator")
        headers = {"x-ratelimit-limit": "10", "x-ratelimit-remaining": "0"}
        gen = TogetherImageGenerator(api_key="k", max_attempts=1)
        with patch("urllib.request.urlopen",
                   return_value=_ok_response(_png_bytes(), headers=headers)):
            gen.generate("x")
        warning_msgs = [r.message for r in caplog.records if r.levelname == "WARNING"]
        assert any("x-ratelimit-remaining" in m for m in warning_msgs)
