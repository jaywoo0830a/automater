"""
tests/test_seo_job_integration.py
-----------------------------------
SEOOption 이 NaverBlogJob 에 올바르게 연결되는지 검증한다.

핵심 계약
---------
1. with_seo() 로 SEOOption 을 주입할 수 있다.
2. SEOOption 이 있으면 단락마다 to_prompt() 로 생성한 프롬프트가 ParagraphGenerator 에 전달된다.
3. SEOOption 이 없으면 content.paragraph_prompt 를 그대로 사용한다 (하위 호환).
4. 단락 인덱스(0-based)와 총 단락 수가 to_prompt() 에 올바르게 전달된다.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from automator.job import NaverBlogJob
from automator.options import AccountOption, TitleOption, ContentOption, MetaOption, SEOOption
from automator.seo_prompt import to_prompt
from automator.paragraph_generator import _STUB_PARAGRAPHS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account():
    return AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")


def _run(layout, seo=None, paragraph_prompt=""):
    """Run a job and return (prompts_passed_to_generator, written_texts)."""
    prompts_received = []

    def fake_generator(prompt):
        prompts_received.append(prompt)
        mock = MagicMock()
        mock.generate.side_effect = _stub_generate
        return mock

    editor = MagicMock()

    with patch("automator.job.ParagraphGenerator", side_effect=fake_generator):
        job = (
            NaverBlogJob
            .for_account(_account())
            .with_title(TitleOption(fixed_title="T"))
            .with_content(ContentOption(
                layout=layout,
                paragraph_prompt=paragraph_prompt,
            ))
            .with_meta(MetaOption())
        )
        if seo:
            job = job.with_seo(seo)
        job.run(editor)

    written = [c.args[0] for c in editor.write_paragraph.call_args_list]
    return prompts_received, written


_stub_cycle = [0]
def _stub_generate(n):
    results = []
    for _ in range(n):
        results.append(_STUB_PARAGRAPHS[_stub_cycle[0] % len(_STUB_PARAGRAPHS)])
        _stub_cycle[0] += 1
    return results


# ---------------------------------------------------------------------------
# with_seo() builder
# ---------------------------------------------------------------------------

class TestWithSeoBuilder:

    def test_with_seo_returns_new_job(self):
        job  = NaverBlogJob.for_account(_account())
        seo  = SEOOption(keyword="강남 수학 과외")
        job2 = job.with_seo(seo)
        assert job2 is not job

    def test_with_seo_does_not_mutate_original(self):
        job  = NaverBlogJob.for_account(_account())
        seo  = SEOOption(keyword="강남 수학 과외")
        job.with_seo(seo)
        assert job._seo is None

    def test_with_seo_stores_option(self):
        seo  = SEOOption(keyword="강남 수학 과외")
        job  = NaverBlogJob.for_account(_account()).with_seo(seo)
        assert job._seo is seo


# ---------------------------------------------------------------------------
# SEOOption → per-paragraph prompts
# ---------------------------------------------------------------------------

class TestSeoPromptPerParagraph:

    def test_seo_generates_one_prompt_per_paragraph(self):
        seo = SEOOption(keyword="강남 수학 과외")
        prompts, _ = _run(["Paragraph 1", "Paragraph 2", "Paragraph 3"], seo=seo)
        assert len(prompts) == 3

    def test_each_prompt_differs_by_position(self):
        """첫/중간/마지막 단락 프롬프트가 모두 달라야 한다."""
        seo = SEOOption(
            keyword="강남 수학 과외",
            keyword_count_first=3,
            keyword_count_others=1,
            keyword_count_last=2,
        )
        prompts, _ = _run(["Paragraph 1", "Paragraph 2", "Paragraph 3"], seo=seo)
        assert prompts[0] != prompts[1]  # first ≠ middle
        assert prompts[1] != prompts[2]  # middle ≠ last

    def test_first_prompt_contains_keyword_count_first(self):
        seo = SEOOption(keyword="강남 수학 과외", keyword_count_first=3)
        prompts, _ = _run(["Paragraph 1", "Paragraph 2"], seo=seo)
        assert "3회" in prompts[0]

    def test_last_prompt_contains_keyword_count_last(self):
        seo = SEOOption(keyword="강남 수학 과외", keyword_count_last=2)
        prompts, _ = _run(["Paragraph 1", "Paragraph 2"], seo=seo)
        assert "2회" in prompts[1]

    def test_first_prompt_contains_cta_when_single_paragraph(self):
        """단락 1개면 첫 단락이자 마지막 — CTA 포함"""
        seo = SEOOption(keyword="강남 수학 과외", include_cta=True)
        prompts, _ = _run(["Paragraph 1"], seo=seo)
        assert "댓글" in prompts[0] or "저장" in prompts[0]

    def test_prompt_index_matches_paragraph_order(self):
        """layout 에서 Paragraph 1 이 먼저여도 인덱스 0 으로 전달"""
        seo = SEOOption(keyword="강남 수학 과외", keyword_count_first=5)
        prompts, _ = _run(["Paragraph 1", "Paragraph 2"], seo=seo)
        assert "5회" in prompts[0]


# ---------------------------------------------------------------------------
# 하위 호환 — SEOOption 없을 때
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    def test_no_seo_uses_paragraph_prompt(self):
        """SEOOption 없으면 paragraph_prompt 를 그대로 ParagraphGenerator 에 전달"""
        prompts, _ = _run(
            ["Paragraph 1", "Paragraph 2"],
            seo=None,
            paragraph_prompt="기존 프롬프트",
        )
        # 모든 단락에 동일한 prompt
        assert all(p == "기존 프롬프트" for p in prompts)

    def test_no_seo_no_prompt_uses_stub(self):
        """SEOOption 도 paragraph_prompt 도 없으면 스텁 텍스트 사용"""
        _, written = _run(["Paragraph 1"], seo=None, paragraph_prompt="")
        # 스텁은 UDHR 텍스트를 순환 — _STUB_PARAGRAPHS 목록 안에 있으면 됨
        assert written[0] in _STUB_PARAGRAPHS

    def test_seo_takes_priority_over_paragraph_prompt(self):
        """SEOOption 과 paragraph_prompt 가 모두 있으면 SEOOption 우선"""
        seo = SEOOption(keyword="강남 수학 과외", keyword_count_first=3)
        prompts, _ = _run(
            ["Paragraph 1"],
            seo=seo,
            paragraph_prompt="무시될 기존 프롬프트",
        )
        assert "3회" in prompts[0]
        assert "무시될 기존 프롬프트" not in prompts[0]
