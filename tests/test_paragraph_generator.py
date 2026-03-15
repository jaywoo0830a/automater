"""
tests/test_paragraph_generator.py
-----------------------------------
Unit tests for ParagraphGenerator.

API 호출은 전부 Mock. 실제 Gemini 호출은 test_blog_e2e.py 에 있다.
"""

import pytest
from unittest.mock import MagicMock, patch

from automator.paragraph_generator import ParagraphGenerator


@pytest.fixture
def gen(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return ParagraphGenerator(prompt="테스트 프롬프트")


# ===========================================================================
# 생성자
# ===========================================================================

@pytest.mark.unit
def test_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        ParagraphGenerator(prompt="p")


@pytest.mark.unit
def test_explicit_key_overrides_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    g = ParagraphGenerator(prompt="p", api_key="explicit-key")
    assert g._api_key == "explicit-key"


@pytest.mark.unit
def test_env_key_is_used(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    g = ParagraphGenerator(prompt="p")
    assert g._api_key == "env-key"


# ===========================================================================
# generate()
# ===========================================================================

@pytest.mark.unit
def test_generate_returns_correct_count(gen):
    with patch.object(gen, "_call_api", return_value='["a","b","c"]'):
        result = gen.generate(3)
    assert len(result) == 3


@pytest.mark.unit
def test_generate_zero_returns_empty(gen):
    assert gen.generate(0) == []


@pytest.mark.unit
def test_generate_falls_back_on_api_error(gen):
    with patch.object(gen, "_call_api", side_effect=Exception("API 오류")):
        result = gen.generate(2)
    assert len(result) == 2
    assert all("실패" in p for p in result)


@pytest.mark.unit
def test_generate_falls_back_on_parse_error(gen):
    with patch.object(gen, "_call_api", return_value="invalid json"):
        result = gen.generate(2)
    assert len(result) == 2


# ===========================================================================
# _parse()
# ===========================================================================

@pytest.mark.unit
def test_parse_json_array(gen):
    assert gen._parse('["단락1","단락2"]', 2) == ["단락1", "단락2"]


@pytest.mark.unit
def test_parse_strips_markdown_fences(gen):
    raw = '```json\n["단락1","단락2"]\n```'
    assert gen._parse(raw, 2) == ["단락1", "단락2"]


@pytest.mark.unit
def test_parse_pads_short_response(gen):
    result = gen._parse('["단락1"]', 3)
    assert len(result) == 3


@pytest.mark.unit
def test_parse_truncates_long_response(gen):
    result = gen._parse('["a","b","c","d"]', 2)
    assert len(result) == 2


@pytest.mark.unit
def test_parse_raises_on_no_json(gen):
    with pytest.raises(ValueError):
        gen._parse("그냥 텍스트", 1)


# ===========================================================================
# job 통합 (conftest의 mock_paragraph_generator 사용)
# ===========================================================================

@pytest.mark.unit
def test_job_uses_generator_when_prompt_set(mock_paragraph_generator):
    """paragraph_prompt 설정 시 mock generator 텍스트가 editor에 전달된다."""
    from automator.job import NaverBlogJob
    from automator.options import AccountOption, TitleOption, ContentOption
    from unittest.mock import MagicMock

    editor = MagicMock()
    (
        NaverBlogJob
        .for_account(AccountOption(naver_id="id", naver_pw="pw", blog_id="blog"))
        .with_title(TitleOption())
        .with_content(ContentOption(
            layout=["Paragraph 1", "Paragraph 2"],
            paragraph_prompt="테스트 프롬프트",
        ))
        .run(editor)
    )
    written = [c.args[0] for c in editor.write_paragraph.call_args_list]
    assert all("mock" in t for t in written)


@pytest.mark.unit
def test_job_uses_placeholder_when_no_prompt(mock_paragraph_generator):
    """paragraph_prompt 없으면 placeholder 텍스트가 editor에 전달된다."""
    from automator.job import NaverBlogJob
    from automator.options import AccountOption, TitleOption, ContentOption
    from unittest.mock import MagicMock

    editor = MagicMock()
    (
        NaverBlogJob
        .for_account(AccountOption(naver_id="id", naver_pw="pw", blog_id="blog"))
        .with_title(TitleOption())
        .with_content(ContentOption(layout=["Paragraph 1"]))
        .run(editor)
    )
    written = [c.args[0] for c in editor.write_paragraph.call_args_list]
    assert all("생성 필요" in t for t in written)
