"""
tests/conftest.py
------------------
Shared pytest fixtures and auto-use mocks.

ParagraphGenerator auto-mock
-----------------------------
Unit and e2e tests must never make real Gemini API calls.
The ``mock_paragraph_generator`` fixture is applied automatically to every
test that is NOT marked ``e2e``, replacing ParagraphGenerator with a stub
that returns predictable placeholder text.

For e2e tests, the real ParagraphGenerator is used but still requires
GEMINI_API_KEY to be set in .env — if the prompt is empty, no call is made.
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Auto-mock: ParagraphGenerator (unit tests only)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_paragraph_generator(request):
    """
    Automatically replace ParagraphGenerator with a stub for all non-e2e tests.

    The stub's generate(count) returns ["(단락 N mock)" for N in 1..count].
    This prevents accidental real API calls and keeps unit tests fast and
    deterministic.

    e2e tests are excluded — they use real (or skipped) API calls based on
    whether GEMINI_API_KEY and paragraph_prompt are set.
    """
    if "e2e" in request.keywords:
        yield  # e2e tests: use real ParagraphGenerator
        return

    def fake_generate(count: int) -> list[str]:
        return [f"(단락 {i} mock)" for i in range(1, count + 1)]

    mock = MagicMock()
    mock.return_value.generate.side_effect = fake_generate

    with patch("automator.job.ParagraphGenerator", mock):
        yield mock
