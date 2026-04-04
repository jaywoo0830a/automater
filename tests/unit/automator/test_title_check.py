"""
tests/unit/automator/test_title_check.py
-------------------------------------------
Unit tests for generate_unique_title() and extract_keyword_query().
"""

from __future__ import annotations

import pytest

from automator.options import TitleOption
from automator.ports import TitleChecker
from automator.title_generator import (
    extract_keyword_query,
    generate_title,
    generate_unique_title,
)


# ---------------------------------------------------------------------------
# Stub checker
# ---------------------------------------------------------------------------

class StubChecker(TitleChecker):
    """Returns True for titles in the duplicates set."""

    def __init__(self, duplicates: set[str] | None = None):
        self.duplicates = duplicates or set()
        self.checked: list[tuple[str, str]] = []

    def is_duplicate(self, title: str, query: str) -> bool:
        self.checked.append((title, query))
        return title in self.duplicates


# ---------------------------------------------------------------------------
# extract_keyword_query
# ---------------------------------------------------------------------------

class TestExtractKeywordQuery:

    def test_strips_pool_token(self):
        opt = TitleOption(
            template="{keyword:region} 중등 {keyword:subject}학원 {pool:hook}",
            values={"region": "대치동", "subject": "수학"},
            pools={"hook": ("솔직 리뷰",)},
        )
        assert extract_keyword_query(opt) == "대치동 중등 수학학원"

    def test_pool_at_start(self):
        opt = TitleOption(
            template="{pool:prefix} {keyword:region} {keyword:subject} 과외",
            values={"region": "강남", "subject": "수학"},
            pools={"prefix": ("검증된",)},
        )
        assert extract_keyword_query(opt) == "강남 수학 과외"

    def test_multiple_pools_stripped(self):
        opt = TitleOption(
            template="{pool:prefix} {keyword:region} {keyword:subject} 과외 {pool:suffix}",
            values={"region": "강남", "subject": "수학"},
            pools={"prefix": ("검증된",), "suffix": ("강력 추천",)},
        )
        assert extract_keyword_query(opt) == "강남 수학 과외"

    def test_no_pool_returns_full(self):
        opt = TitleOption(
            template="{keyword:region} 중등 {keyword:subject}학원",
            values={"region": "대치동", "subject": "수학"},
        )
        assert extract_keyword_query(opt) == "대치동 중등 수학학원"

    def test_glued_tokens_no_extra_space(self):
        opt = TitleOption(
            template="{keyword:region}{keyword:subject}과외 {pool:hook}",
            values={"region": "강남", "subject": "수학"},
            pools={"hook": ("추천",)},
        )
        assert extract_keyword_query(opt) == "강남수학과외"

    def test_collapses_double_spaces(self):
        """Pool between keywords → double space → collapsed."""
        opt = TitleOption(
            template="{keyword:region} {pool:mid} {keyword:subject}학원",
            values={"region": "대치동", "subject": "수학"},
            pools={"mid": ("중등",)},
        )
        # pool removed → "대치동  수학학원" → "대치동 수학학원"
        assert extract_keyword_query(opt) == "대치동 수학학원"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def option() -> TitleOption:
    return TitleOption(
        template="{keyword:region} 중등 {keyword:subject}학원 {pool:hook}",
        values={"region": "수월동", "subject": "수학"},
        pools={"hook": ("솔직 리뷰", "학부모 후기", "실제 경험담", "추천 BEST", "비교 분석")},
    )


# ---------------------------------------------------------------------------
# generate_unique_title
# ---------------------------------------------------------------------------

class TestGenerateUniqueTitle:

    def test_returns_first_if_no_duplicate(self, option):
        checker = StubChecker(duplicates=set())
        title = generate_unique_title(option, checker, max_attempts=5)
        assert "수월동" in title
        assert "수학" in title
        assert len(checker.checked) == 1

    def test_retries_on_duplicate(self, option):
        # Generate the first title to mark it as duplicate
        first_option = TitleOption(
            template=option.template,
            values=option.values,
            pools=option.pools,
            seed=0,
        )
        first_title = generate_title(first_option)

        checker = StubChecker(duplicates={first_title})
        title = generate_unique_title(option, checker, max_attempts=10)
        assert len(checker.checked) >= 2
        assert title not in checker.duplicates

    def test_query_is_keyword_only(self, option):
        """checker receives keyword-only query, not full title."""
        checker = StubChecker()
        generate_unique_title(option, checker, max_attempts=1)

        title, query = checker.checked[0]
        assert query == "수월동 중등 수학학원"
        assert "수월동" in title
        # query has no hook phrase
        for hook in ("솔직 리뷰", "학부모 후기", "실제 경험담", "추천 BEST", "비교 분석"):
            assert hook not in query

    def test_query_is_same_across_retries(self, option):
        """Query stays fixed — only title changes across retries."""
        first_option = TitleOption(
            template=option.template,
            values=option.values,
            pools=option.pools,
            seed=0,
        )
        first_title = generate_title(first_option)

        checker = StubChecker(duplicates={first_title})
        generate_unique_title(option, checker, max_attempts=5)

        queries = [q for _, q in checker.checked]
        assert all(q == "수월동 중등 수학학원" for q in queries)

    def test_returns_last_on_exhaustion(self):
        option = TitleOption(
            template="{keyword:region} {pool:hook}",
            values={"region": "강남"},
            pools={"hook": ("A",)},
        )
        checker = StubChecker(duplicates={"강남 A"})
        title = generate_unique_title(option, checker, max_attempts=3)
        assert title == "강남 A"

    def test_skips_already_seen_titles(self):
        option = TitleOption(
            template="{keyword:region} {pool:hook}",
            values={"region": "강남"},
            pools={"hook": ("A", "B")},
        )
        checker = StubChecker(duplicates={"강남 A", "강남 B"})
        generate_unique_title(option, checker, max_attempts=10)
        unique_checks = {t for t, _ in checker.checked}
        assert len(unique_checks) <= 2

    def test_max_attempts_respected(self, option):
        checker = StubChecker(duplicates={
            f"수월동 중등 수학학원 {h}"
            for h in ("솔직 리뷰", "학부모 후기", "실제 경험담", "추천 BEST", "비교 분석")
        })
        generate_unique_title(option, checker, max_attempts=3)
        assert len(checker.checked) <= 3

    def test_keyword_values_are_fixed(self, option):
        checker = StubChecker(duplicates=set())
        title = generate_unique_title(option, checker, max_attempts=5)
        assert "수월동" in title
        assert "수학" in title
