"""
tests/unit/automator/test_naver_checker.py
--------------------------------------------
Unit tests for PlaywrightTitleChecker and helpers.
"""

from __future__ import annotations

import pytest

from automator.naver_checker import PlaywrightTitleChecker, _normalize, _parse_delay


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------

class TestNormalize:

    def test_collapses_whitespace(self):
        assert _normalize("강남  수학   과외") == "강남 수학 과외"

    def test_strips(self):
        assert _normalize("  강남 수학  ") == "강남 수학"

    def test_lowercases(self):
        assert _normalize("ABC DEF") == "abc def"

    def test_empty(self):
        assert _normalize("") == ""


# ---------------------------------------------------------------------------
# _parse_delay
# ---------------------------------------------------------------------------

class TestParseDelay:

    def test_single_seconds(self):
        assert _parse_delay("2s") == (2.0, 2.0)

    def test_range_seconds(self):
        assert _parse_delay("1s ~ 3s") == (1.0, 3.0)

    def test_milliseconds(self):
        assert _parse_delay("500ms") == (0.5, 0.5)

    def test_mixed_range(self):
        assert _parse_delay("500ms ~ 2s") == (0.5, 2.0)

    def test_default_on_empty(self):
        assert _parse_delay("") == (1.0, 2.0)

    def test_bare_number(self):
        assert _parse_delay("1.5") == (1.5, 1.5)

    def test_reversed_range_is_sorted(self):
        lo, hi = _parse_delay("3s ~ 1s")
        assert lo <= hi


# ---------------------------------------------------------------------------
# PlaywrightTitleChecker — with mock page
# ---------------------------------------------------------------------------

class FakeElement:
    def __init__(self, text: str):
        self._text = text

    def inner_text(self) -> str:
        return self._text


class FakePage:
    """Minimal Playwright Page mock for title checker tests."""

    def __init__(self, result_titles: list[str] | None = None):
        self._result_titles = result_titles or []
        self._goto_url: str = ""

    def goto(self, url: str) -> None:
        self._goto_url = url

    def wait_for_load_state(self, state: str) -> None:
        pass

    def wait_for_selector(self, selector: str, **kwargs) -> None:
        if not self._result_titles:
            raise TimeoutError("no results")

    def query_selector_all(self, selector: str) -> list[FakeElement]:
        return [FakeElement(t) for t in self._result_titles]


# ---------------------------------------------------------------------------
# is_duplicate(title, query)
# ---------------------------------------------------------------------------

class TestIsDuplicateExact:

    def test_no_results_is_not_duplicate(self):
        page = FakePage(result_titles=[])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is False

    def test_exact_match_is_duplicate(self):
        page = FakePage(result_titles=["대치동 중등 수학과외 강력 추천"])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is True

    def test_different_hook_is_not_duplicate(self):
        """같은 키워드지만 후킹 문구가 다르면 중복 아님."""
        page = FakePage(result_titles=["대치동 중등 수학과외 학부모 후기"])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is False

    def test_whitespace_normalized_match(self):
        page = FakePage(result_titles=["대치동  중등  수학과외  강력 추천"])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is True

    def test_partial_match_not_duplicate_in_exact_mode(self):
        page = FakePage(result_titles=["대치동 중등 수학과외 강력 추천 후기 정리"])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is False

    def test_multiple_results_one_match(self):
        page = FakePage(result_titles=[
            "고잔동 중등 수학과외 후기",
            "대치동 중등 수학과외 강력 추천",
            "관저동 영어학원 추천",
        ])
        checker = PlaywrightTitleChecker(page, delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is True


class TestIsDuplicateContains:

    def test_contains_match(self):
        page = FakePage(result_titles=["대치동 중등 수학과외 강력 추천 후기 정리"])
        checker = PlaywrightTitleChecker(page, match="contains", delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is True

    def test_no_contains_match(self):
        page = FakePage(result_titles=["고잔동 중등 수학과외 후기"])
        checker = PlaywrightTitleChecker(page, match="contains", delay="0s")
        assert checker.is_duplicate("대치동 중등 수학과외 강력 추천", "대치동 중등 수학과외") is False


# ---------------------------------------------------------------------------
# URL format — query only, spaces as +
# ---------------------------------------------------------------------------

class TestURLFormat:

    def test_unified_search_no_where_param(self):
        """통합검색 — where=blog 없음."""
        page = FakePage(result_titles=[])
        checker = PlaywrightTitleChecker(page, delay="0s")
        checker.is_duplicate("대치동 수학과외 추천", "대치동 수학과외")
        assert "where=blog" not in page._goto_url

    def test_spaces_encoded_as_plus(self):
        """띄어쓰기가 + 로 인코딩."""
        page = FakePage(result_titles=[])
        checker = PlaywrightTitleChecker(page, delay="0s")
        checker.is_duplicate("대치동 수학과외 추천", "대치동 수학과외")
        # query part: "대치동+수학과외"  (not the full title)
        assert "%EB%8C%80%EC%B9%98%EB%8F%99+%EC%88%98%ED%95%99%EA%B3%BC%EC%99%B8" in page._goto_url

    def test_query_used_not_full_title(self):
        """검색 URL에는 query(키워드부)만 사용, 풀 타이틀 아님."""
        page = FakePage(result_titles=[])
        checker = PlaywrightTitleChecker(page, delay="0s")
        checker.is_duplicate(
            "대치동 중등 수학과외 강력 추천 정리",
            "대치동 중등 수학과외",
        )
        url = page._goto_url
        # "강력" should NOT be in the URL
        assert "%EA%B0%95%EB%A0%A5" not in url
        # "대치동" SHOULD be in the URL
        assert "%EB%8C%80%EC%B9%98%EB%8F%99" in url
