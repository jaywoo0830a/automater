"""
tests/test_paragraph_generator.py
-----------------------------------
Unit tests for ParagraphGenerator.

All Gemini API calls are mocked — no real network requests are made.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from automator.paragraph_generator import ParagraphGenerator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_generator(prompt: str = "테스트 프롬프트") -> ParagraphGenerator:
    """Return a ParagraphGenerator with a dummy API key."""
    return ParagraphGenerator(prompt=prompt, api_key="dummy-key")


def _mock_response(texts: list[str]) -> MagicMock:
    """Return a mock Gemini response whose .text is a JSON array."""
    mock = MagicMock()
    mock.text = json.dumps(texts, ensure_ascii=False)
    return mock


# ---------------------------------------------------------------------------
# 1. Construction
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_raises_without_api_key():
    """API 키 없이 생성하면 ValueError."""
    with patch.dict("os.environ", {}, clear=True):
        # make sure GEMINI_API_KEY is not set
        import os
        os.environ.pop("GEMINI_API_KEY", None)
        with pytest.raises(ValueError, match="Gemini API key"):
            ParagraphGenerator(prompt="test")


@pytest.mark.unit
def test_accepts_api_key_from_env(monkeypatch):
    """GEMINI_API_KEY 환경변수에서 API 키를 읽는다."""
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    gen = ParagraphGenerator(prompt="test")
    assert gen._api_key == "env-key"


@pytest.mark.unit
def test_explicit_key_overrides_env(monkeypatch):
    """명시적 api_key가 환경변수보다 우선한다."""
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    gen = ParagraphGenerator(prompt="test", api_key="explicit-key")
    assert gen._api_key == "explicit-key"


# ---------------------------------------------------------------------------
# 2. generate() — happy path
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_returns_correct_count():
    """generate(3)이 정확히 3개의 단락을 반환한다."""
    gen = _make_generator()
    texts = ["단락1", "단락2", "단락3"]
    with patch.object(gen, "_call_api", return_value=json.dumps(texts)):
        result = gen.generate(3)
    assert len(result) == 3


@pytest.mark.unit
def test_generate_returns_correct_text():
    """반환된 단락 내용이 API 응답과 일치한다."""
    gen = _make_generator()
    texts = ["첫 번째 단락입니다.", "두 번째 단락입니다."]
    with patch.object(gen, "_call_api", return_value=json.dumps(texts)):
        result = gen.generate(2)
    assert result == texts


@pytest.mark.unit
def test_generate_zero_returns_empty():
    """count=0이면 API를 호출하지 않고 빈 리스트를 반환한다."""
    gen = _make_generator()
    with patch.object(gen, "_call_api") as mock_api:
        result = gen.generate(0)
    assert result == []
    mock_api.assert_not_called()


# ---------------------------------------------------------------------------
# 3. _parse() — JSON handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_strips_markdown_fences():
    """```json ... ``` 코드 펜스를 제거하고 파싱한다."""
    gen = _make_generator()
    raw = '```json\n["단락1", "단락2"]\n```'
    result = gen._parse(raw, 2)
    assert result == ["단락1", "단락2"]


@pytest.mark.unit
def test_parse_strips_plain_fences():
    """``` ... ``` 코드 펜스(언어 없음)도 제거한다."""
    gen = _make_generator()
    raw = '```\n["단락1"]\n```'
    result = gen._parse(raw, 1)
    assert result == ["단락1"]


@pytest.mark.unit
def test_parse_pads_short_response():
    """API가 count보다 적게 반환하면 placeholder로 채운다."""
    gen = _make_generator()
    raw = json.dumps(["단락1"])
    result = gen._parse(raw, 3)
    assert len(result) == 3
    assert result[0] == "단락1"
    assert "생성 실패" in result[1]
    assert "생성 실패" in result[2]


@pytest.mark.unit
def test_parse_truncates_long_response():
    """API가 count보다 많이 반환하면 앞에서 잘라낸다."""
    gen = _make_generator()
    raw = json.dumps(["단락1", "단락2", "단락3", "단락4"])
    result = gen._parse(raw, 2)
    assert result == ["단락1", "단락2"]


@pytest.mark.unit
def test_parse_raises_on_no_json_array():
    """JSON 배열이 없으면 ValueError를 발생시킨다."""
    gen = _make_generator()
    with pytest.raises(ValueError, match="No JSON array found"):
        gen._parse("이것은 JSON이 아닙니다.", 2)


# ---------------------------------------------------------------------------
# 4. generate() — fallback on error
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_fallback_on_api_error():
    """API 호출 실패 시 placeholder 리스트를 반환한다 (예외를 올리지 않음)."""
    gen = _make_generator()
    with patch.object(gen, "_call_api", side_effect=Exception("network error")):
        result = gen.generate(2)
    assert len(result) == 2
    assert all("생성 실패" in p for p in result)


@pytest.mark.unit
def test_generate_fallback_on_parse_error():
    """응답 파싱 실패 시 placeholder 리스트를 반환한다."""
    gen = _make_generator()
    with patch.object(gen, "_call_api", return_value="완전히 잘못된 응답"):
        result = gen.generate(2)
    assert len(result) == 2
    assert all("생성 실패" in p for p in result)


# ---------------------------------------------------------------------------
# 5. job.py 연동 — paragraph_prompt 분기
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_job_uses_gemini_when_prompt_set(mock_paragraph_generator):
    """
    ContentOption.paragraph_prompt가 설정되면 ParagraphGenerator를 호출한다.
    conftest의 mock_paragraph_generator가 자동 주입된다.
    """
    from automator.job import NaverBlogJob
    from automator.options import AccountOption, TitleOption, ContentOption

    class MockEditor:
        def __init__(self): self.actions = []
        def _r(self, n, *a): self.actions.append((n, *a))
        def open(self):                           self._r("open")
        def write_title(self, t):                 self._r("write_title", t)
        def write_paragraph(self, t, newlines=2): self._r("write_paragraph", t)
        def upload_image(self, p):                self._r("upload_image", p)
        def set_representative_image(self, i):    self._r("set_rep", i)
        def move_cursor_to_end(self):             self._r("move_cursor")
        def publish(self):                        self._r("publish")

    account = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    content = ContentOption(
        layout=["Paragraph 1", "Paragraph 2"],
        paragraph_prompt="대치동 수학 과외 홍보",
    )
    job = NaverBlogJob.for_account(account).with_title(TitleOption()).with_content(content)
    editor = MockEditor()
    job.run(editor)

    # conftest stub: generate(2) → ["(단락 1 mock)", "(단락 2 mock)"]
    mock_paragraph_generator.assert_called_once_with(prompt="대치동 수학 과외 홍보")
    mock_paragraph_generator.return_value.generate.assert_called_once_with(2)
    para_texts = [a[1] for a in editor.actions if a[0] == "write_paragraph"]
    assert para_texts == ["(단락 1 mock)", "(단락 2 mock)"]


@pytest.mark.unit
def test_job_uses_placeholder_when_no_prompt(mock_paragraph_generator):
    """paragraph_prompt가 없으면 ParagraphGenerator를 호출하지 않는다."""
    from automator.job import NaverBlogJob
    from automator.options import AccountOption, TitleOption, ContentOption

    class MockEditor:
        def __init__(self): self.actions = []
        def _r(self, n, *a): self.actions.append((n, *a))
        def open(self):                           self._r("open")
        def write_title(self, t):                 self._r("write_title", t)
        def write_paragraph(self, t, newlines=2): self._r("write_paragraph", t)
        def upload_image(self, p):                self._r("upload_image", p)
        def set_representative_image(self, i):    self._r("set_rep", i)
        def move_cursor_to_end(self):             self._r("move_cursor")
        def publish(self):                        self._r("publish")

    account = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    content = ContentOption(layout=["Paragraph 1"])
    job = NaverBlogJob.for_account(account).with_title(TitleOption()).with_content(content)
    editor = MockEditor()
    job.run(editor)

    mock_paragraph_generator.assert_not_called()
    para_texts = [a[1] for a in editor.actions if a[0] == "write_paragraph"]
    assert para_texts == ["(단락 1 생성 필요)"]
