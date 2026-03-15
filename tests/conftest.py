"""
tests/conftest.py
------------------
Shared pytest fixtures and auto-use mocks.

ParagraphGenerator mock policy
--------------------------------
ParagraphGenerator is ENV-aware and handles mocking itself:

    ENV=production  → real Gemini API (paragraph_generator.py handles this)
    ENV=dev | test  → UDHR stub paragraphs (paragraph_generator.py handles this)

The fixture below patches ParagraphGenerator at the job layer for unit tests
only — this prevents even importing google-genai and keeps unit tests fully
isolated from the application environment.

For e2e tests the real ParagraphGenerator class is used, and it will return
UDHR stub paragraphs unless ENV=production is explicitly set.
"""

from unittest.mock import MagicMock, patch

import pytest

from automator.paragraph_generator import _stub_generate


# ---------------------------------------------------------------------------
# Auto-patch: ParagraphGenerator (unit tests only)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_paragraph_generator(request):
    """
    Patch ParagraphGenerator at the job layer for all unit tests.

    This replaces the class entirely so google-genai is never imported,
    making unit tests fast regardless of the ENV variable.

    E2e tests are excluded — they use the real class which respects ENV.
    """
    if "e2e" in request.keywords:
        yield  # e2e: ParagraphGenerator handles mocking via ENV
        return

    mock = MagicMock()
    mock.return_value.generate.side_effect = _stub_generate

    with patch("automator.job.ParagraphGenerator", mock):
        yield mock
