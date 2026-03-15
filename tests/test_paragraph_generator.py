"""
tests/test_paragraph_generator.py
-----------------------------------
Unit tests for ParagraphGenerator.

ENV policy
----------
ParagraphGenerator은 ENV 변수에 따라 동작이 달라진다:
  ENV=dev | test  → UDHR 스텁 단락 반환 (API 호출 없음)
  ENV=production  → 실제 Gemini API 호출

모든 unit 테스트는 ENV=dev(기본값)에서 실행되므로 실제 API 호출은 발생하지 않는다.
production 경로 테스트는 monkeypatch로 ENV=production을 설정한 뒤 _call_api를 패치한다.
"""

import pytest
from unittest.mock import MagicMock, patch

from automator.paragraph_generator import ParagraphGenerator, _stub_generate


@pytest.fixture
def dev_gen(monkeypatch):
    """ENV=dev (기본값) ParagraphGenerator — UDHR 스텁 단락 반환."""
    monkeypatch.setenv("ENV", "dev")
    return ParagraphGenerator(prompt="테스트 프롬프트")


@pytest.fixture
def prod_gen(monkeypatch):
    """ENV=production ParagraphGenerator — 실제 API 경로 (api_key 필요)."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    return ParagraphGenerator(prompt="테스트 프롬프트")


# gen = prod_gen alias — _call_api, _parse 테스트에 사용
gen = prod_gen


# ===========================================================================
# 생성자 — ENV별 동작
# ===========================================================================

@pytest.mark.unit
def test_dev_env_does_not_require_api_key(monkeypatch):
    """ENV=dev에서는 GEMINI_API_KEY 없어도 생성 가능."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    g = ParagraphGenerator(prompt="p")   # must not raise
    assert not g._production


@pytest.mark.unit
def test_test_env_does_not_require_api_key(monkeypatch):
    """ENV=test에서도 GEMINI_API_KEY 없이 생성 가능하고 _production=False."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gen = ParagraphGenerator(prompt="p")
    assert gen._production is False


@pytest.mark.unit
def test_production_env_requires_api_key(monkeypatch):
    """ENV=production에서 GEMINI_API_KEY 없으면 ValueError."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        ParagraphGenerator(prompt="p")


@pytest.mark.unit
def test_explicit_key_overrides_env(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    g = ParagraphGenerator(prompt="p", api_key="explicit-key")
    assert g._api_key == "explicit-key"


@pytest.mark.unit
def test_env_key_is_used_in_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    g = ParagraphGenerator(prompt="p")
    assert g._api_key == "env-key"


# ===========================================================================
# generate()
# ===========================================================================

@pytest.mark.unit
def test_generate_returns_correct_count_dev(dev_gen):
    """ENV=dev: _call_api 패치 없이도 count개 UDHR 스텁 단락 반환."""
    result = dev_gen.generate(3)
    assert len(result) == 3


@pytest.mark.unit
def test_generate_returns_correct_count_prod(prod_gen):
    """ENV=production: _call_api 경로 사용."""
    with patch.object(prod_gen, "_call_api", return_value='["a","b","c"]'):
        result = prod_gen.generate(3)
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
def test_job_uses_generator_when_prompt_set():
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
    assert len(written) == 2
    from automator.paragraph_generator import _STUB_PARAGRAPHS
    assert written[0] == _STUB_PARAGRAPHS[0]
    assert written[1] == _STUB_PARAGRAPHS[1]


@pytest.mark.unit
def test_job_uses_stub_when_no_prompt():
    """
    paragraph_prompt 없으면 ParagraphGenerator를 빈 prompt로 호출해
    스텁(UDHR) 텍스트가 editor에 전달된다.
    "(단락 N 생성 필요)" 하드코딩은 더 이상 사용하지 않는다.
    """
    from automator.job import NaverBlogJob
    from automator.options import AccountOption, TitleOption, ContentOption
    from automator.paragraph_generator import _STUB_PARAGRAPHS
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
    assert len(written) == 1
    assert written[0] == _STUB_PARAGRAPHS[0]


# ===========================================================================
# RateLimitError — 429 처리
# ===========================================================================

from automator.paragraph_generator import RateLimitError


def _patch_genai(side_effect):
    """
    Patch `from google import genai` style import.
    Sets google_mock.genai.Client().models.generate_content side_effect.
    """
    import sys
    from unittest.mock import MagicMock, patch

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = side_effect
    fake_genai = MagicMock()
    fake_genai.Client.return_value = fake_client
    google_mock = MagicMock()
    google_mock.genai = fake_genai
    google_mock.genai.types = MagicMock()
    return patch.dict(sys.modules, {
        "google":             google_mock,
        "google.genai":       fake_genai,
        "google.genai.types": MagicMock(),
    })


@pytest.mark.unit
def test_call_api_converts_429_to_rate_limit_error():
    """
    _call_api()에서 429 RESOURCE_EXHAUSTED 예외가 발생하면
    RateLimitError로 변환해서 raise한다.
    """
    gen = ParagraphGenerator(prompt="test", api_key="fake")
    with _patch_genai(Exception("ClientError: 429 RESOURCE_EXHAUSTED quota exceeded")):
        with pytest.raises(RateLimitError, match="rate limit|429"):
            gen._call_api(count=1)


@pytest.mark.unit
def test_call_api_passes_through_non_429_errors():
    """429가 아닌 예외는 RateLimitError로 변환하지 않고 그대로 통과한다."""
    gen = ParagraphGenerator(prompt="test", api_key="fake")
    with _patch_genai(ValueError("bad model config")):
        with pytest.raises(ValueError):
            gen._call_api(count=1)


@pytest.mark.unit
def test_generate_reraises_rate_limit_error(prod_gen):
    """
    ENV=production에서 _call_api가 RateLimitError를 내면 generate()가 re-raise한다.
    """
    with patch.object(prod_gen, "_call_api", side_effect=RateLimitError("daily quota exhausted")):
        with pytest.raises(RateLimitError):
            prod_gen.generate(count=1)


@pytest.mark.unit
def test_generate_returns_placeholder_on_other_errors(prod_gen):
    """
    ENV=production에서 RateLimitError가 아닌 예외는 플레이스홀더를 반환한다.
    """
    with patch.object(prod_gen, "_call_api", side_effect=ConnectionError("network unreachable")):
        result = prod_gen.generate(count=2)
    assert result == ["(단락 1 생성 실패)", "(단락 2 생성 실패)"]


@pytest.mark.unit
def test_rate_limit_error_is_importable_and_is_exception():
    """RateLimitError는 Exception 서브클래스이고 import할 수 있다."""
    from automator.paragraph_generator import RateLimitError as RLE
    assert issubclass(RLE, Exception)
    instance = RLE("quota exceeded")
    assert "quota" in str(instance)


# ===========================================================================
# ENV 기반 동작 분기
# ===========================================================================

@pytest.mark.unit
def test_generate_uses_stub_in_dev(monkeypatch):
    """
    ENV=dev 일 때 generate()는 실제 UDHR 스텁을 반환한다. 통합 검증.
    """
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from automator.paragraph_generator import _STUB_PARAGRAPHS

    gen = ParagraphGenerator(prompt="테스트")
    assert gen._production is False

    result = gen.generate(count=2)
    assert len(result) == 2
    assert result[0] == _STUB_PARAGRAPHS[0]
    assert result[1] == _STUB_PARAGRAPHS[1]


@pytest.mark.unit
def test_generate_uses_stub_in_test_env(monkeypatch):
    """ENV=test 에서도 동일하게 UDHR 스텁이 반환된다."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from automator.paragraph_generator import _STUB_PARAGRAPHS

    gen = ParagraphGenerator(prompt="테스트")
    result = gen.generate(count=3)

    assert len(result) == 3
    for i in range(3):
        assert result[i] == _STUB_PARAGRAPHS[i % len(_STUB_PARAGRAPHS)]


@pytest.mark.unit
def test_stub_cycles_beyond_paragraph_count(monkeypatch):
    """스텁이 5개뿐이어도 6개 이상 요청 시 순환 반환된다."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from automator.paragraph_generator import _STUB_PARAGRAPHS

    gen = ParagraphGenerator(prompt="t")
    result = gen.generate(count=len(_STUB_PARAGRAPHS) + 2)
    assert result[0] == result[len(_STUB_PARAGRAPHS)]
    assert result[1] == result[len(_STUB_PARAGRAPHS) + 1]


@pytest.mark.unit
def test_generate_does_not_call_api_in_dev():
    """ENV=dev 에서 _call_api()가 호출되지 않는다. 대신 _stub_generate()가 사용된다."""
    with patch("automator.paragraph_generator.is_production", return_value=False):
        gen = ParagraphGenerator.__new__(ParagraphGenerator)
        gen._prompt     = "테스트"
        gen._production = False
        gen._api_key    = ""
        gen._model      = ""

        call_api_called = []
        gen._call_api = lambda count: call_api_called.append(count) or "[]"
        gen.generate(count=2)

    assert not call_api_called, "_call_api()가 호출되면 안 됨 (dev)"
