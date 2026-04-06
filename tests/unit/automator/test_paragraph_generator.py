"""
tests/test_paragraph_generator.py
-----------------------------------
Unit tests for generate_paragraph().

ENV=dev | test -> stub paragraphs (UDHR Korean)
ENV=production -> Gemini API (mocked in tests)
"""

import pytest
from unittest.mock import patch

from automator.paragraph_generator import (
    generate_paragraph,
    _stub_generate,
    GeminiError,
    RateLimitError,
    SafetyBlockError,
    EmptyResponseError,
    PromptBlockedError,
    ServerError,
    AuthenticationError,
    InvalidRequestError,
    _STUB_PARAGRAPHS,
)


# ===========================================================================
# ENV-based behavior
# ===========================================================================

def test_dev_env_does_not_require_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = generate_paragraph("p")
    assert isinstance(result, str)
    assert len(result) > 0


def test_test_env_does_not_require_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = generate_paragraph("p")
    assert isinstance(result, str)
    assert len(result) > 0


def test_production_env_requires_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AuthenticationError, match="API key"):
        generate_paragraph("p")


def test_explicit_key_overrides_env(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("automator.paragraph_generator._call_api", return_value="generated text"):
        result = generate_paragraph("p", api_key="explicit-key")
    assert result == "generated text"


# ===========================================================================
# Stub generation (non-production)
# ===========================================================================

def test_generate_uses_stub_in_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    result = generate_paragraph("any prompt")
    assert result == _STUB_PARAGRAPHS[0]


def test_generate_does_not_call_api_in_dev():
    with patch("automator.paragraph_generator.is_production", return_value=False), \
         patch("automator.paragraph_generator._call_api") as mock_api:
        generate_paragraph("p")
    mock_api.assert_not_called()


# ===========================================================================
# Prompt passthrough — no wrapping
# ===========================================================================

def test_prompt_passed_as_is(monkeypatch):
    """generate_paragraph sends the user's prompt to _call_api without modification."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    user_prompt = "강남 수학 과외 홍보 블로그 글을 써주세요."
    with patch("automator.paragraph_generator._call_api", return_value="ok") as mock:
        generate_paragraph(user_prompt)
    assert mock.call_args[0][0] == user_prompt


# ===========================================================================
# Exception hierarchy
# ===========================================================================

def test_all_exceptions_inherit_from_gemini_error():
    for cls in (RateLimitError, SafetyBlockError, EmptyResponseError,
                PromptBlockedError, ServerError, AuthenticationError,
                InvalidRequestError):
        assert issubclass(cls, GeminiError)
        assert issubclass(cls, Exception)


def test_rate_limit_error_is_exception():
    err = RateLimitError("test")
    assert str(err) == "test"


# ===========================================================================
# Error propagation from _call_api
# ===========================================================================

def test_call_api_converts_429_to_rate_limit_error(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=RateLimitError("429")):
        with pytest.raises(RateLimitError):
            generate_paragraph("p")


def test_safety_block_error_propagates(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=SafetyBlockError("SAFETY")):
        with pytest.raises(SafetyBlockError):
            generate_paragraph("p")


def test_empty_response_error_propagates(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=EmptyResponseError("empty")):
        with pytest.raises(EmptyResponseError):
            generate_paragraph("p")


def test_server_error_propagates(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=ServerError("500")):
        with pytest.raises(ServerError):
            generate_paragraph("p")


def test_non_gemini_errors_propagate(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=RuntimeError("connection failed")):
        with pytest.raises(RuntimeError, match="connection"):
            generate_paragraph("p")
