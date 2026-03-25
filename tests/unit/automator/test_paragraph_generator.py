"""
tests/test_paragraph_generator.py
-----------------------------------
Unit tests for generate_paragraphs().

ENV=dev | test -> stub paragraphs (UDHR Korean)
ENV=production -> Gemini API (mocked in tests)
"""

import pytest
from unittest.mock import MagicMock, patch

from automator.paragraph_generator import (
    generate_paragraphs,
    _stub_generate,
    _parse,
    RateLimitError,
    _STUB_PARAGRAPHS,
)


# ===========================================================================
# ENV-based behavior
# ===========================================================================

def test_dev_env_does_not_require_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = generate_paragraphs("p", 1)
    assert len(result) == 1


def test_test_env_does_not_require_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = generate_paragraphs("p", 1)
    assert len(result) == 1


def test_production_env_requires_api_key(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        generate_paragraphs("p", 1)


def test_explicit_key_overrides_env(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("automator.paragraph_generator._call_api", return_value='["text"]'):
        result = generate_paragraphs("p", 1, api_key="explicit-key")
    assert len(result) == 1


# ===========================================================================
# Stub generation (non-production)
# ===========================================================================

def test_generate_returns_correct_count_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    assert len(generate_paragraphs("p", 3)) == 3


def test_generate_zero_returns_empty():
    assert generate_paragraphs("p", 0) == []


def test_generate_negative_returns_empty():
    assert generate_paragraphs("p", -1) == []


def test_generate_uses_stub_in_dev(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    result = generate_paragraphs("any prompt", 2)
    assert result[0] == _STUB_PARAGRAPHS[0]
    assert result[1] == _STUB_PARAGRAPHS[1]


def test_stub_cycles_beyond_paragraph_count(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    result = generate_paragraphs("p", len(_STUB_PARAGRAPHS) + 1)
    assert result[-1] == _STUB_PARAGRAPHS[0]


def test_generate_does_not_call_api_in_dev():
    with patch("automator.paragraph_generator.is_production", return_value=False), \
         patch("automator.paragraph_generator._call_api") as mock_api:
        generate_paragraphs("p", 1)
    mock_api.assert_not_called()


# ===========================================================================
# _parse — JSON array extraction
# ===========================================================================

def test_parse_json_array():
    result = _parse('["a", "b", "c"]', 3)
    assert result == ["a", "b", "c"]


def test_parse_strips_markdown_fences():
    result = _parse('```json\n["a", "b"]\n```', 2)
    assert result == ["a", "b"]


def test_parse_pads_short_response():
    result = _parse('["only one"]', 3)
    assert len(result) == 3
    assert result[0] == "only one"


def test_parse_truncates_long_response():
    result = _parse('["a", "b", "c", "d"]', 2)
    assert result == ["a", "b"]


def test_parse_raises_on_no_json():
    with pytest.raises(ValueError, match="No JSON"):
        _parse("no json here", 1)


def test_parse_raises_on_non_list():
    with pytest.raises(ValueError, match="No JSON array"):
        _parse('{"key": "value"}', 1)


# ===========================================================================
# RateLimitError — 429 handling
# ===========================================================================

def test_rate_limit_error_is_exception():
    assert issubclass(RateLimitError, Exception)
    err = RateLimitError("test")
    assert str(err) == "test"


def test_call_api_converts_429_to_rate_limit_error(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=RateLimitError("429")):
        with pytest.raises(RateLimitError):
            generate_paragraphs("p", 1)


def test_non_429_errors_propagate(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    with patch("automator.paragraph_generator._call_api",
               side_effect=RuntimeError("connection failed")):
        with pytest.raises(RuntimeError, match="connection"):
            generate_paragraphs("p", 1)


# PostingJob integration tests removed — now covered by
# tests/integration/test_content_builder.py
