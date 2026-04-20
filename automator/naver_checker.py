"""
automator/naver_checker.py
---------------------------
Playwright-based Naver title duplicate checker.

Searches Naver unified search (통합검색) with the **keyword-only** part
of the title, then checks whether the **full title** (keyword + hook)
already appears in the results.

Example::

    title = "대치동 중등 수학과외 강력 추천 정리"   # full
    query = "대치동 중등 수학과외"                  # keyword-only

    → search: https://search.naver.com/search.naver?query=대치동+중등+수학과외
    → if "대치동 중등 수학과외 강력 추천 정리" found in results → duplicate

Spaces are encoded as ``+`` (standard query-string convention).

Match modes:
    exact    — normalized full titles must be identical
    contains — full generated title is a substring of a search result title
"""

from __future__ import annotations

import logging
import random
import re
import time
import urllib.parse
from typing import override

from automator.ports import TitleChecker

logger = logging.getLogger(__name__)

_NAVER_SEARCH = "https://search.naver.com/search.naver"
_NORMALIZE_RE = re.compile(r"\s+")

# Naver unified search — headline titles use the SDS design system class.
# This captures blog, cafe, news, and other vertical titles in one selector.
_TITLE_SELECTOR = "span.sds-comps-text-type-headline1"


def _normalize(text: str) -> str:
    """Collapse whitespace, strip, lowercase."""
    return _NORMALIZE_RE.sub(" ", text).strip().lower()


def _parse_delay(raw: str) -> tuple[float, float]:
    """Parse delay DSL string -> (lo, hi) seconds.

    Formats::

        "1s"         -> (1.0, 1.0)
        "1s ~ 2s"    -> (1.0, 2.0)
        "500ms"      -> (0.5, 0.5)
        "500ms ~ 1s" -> (0.5, 1.0)
    """
    if not raw:
        return (1.0, 2.0)

    def _to_seconds(s: str) -> float:
        s = s.strip().lower()
        if s.endswith("ms"):
            return float(s[:-2]) / 1000
        if s.endswith("s"):
            return float(s[:-1])
        return float(s)

    if "~" in raw:
        parts = raw.split("~", 1)
        lo = _to_seconds(parts[0])
        hi = _to_seconds(parts[1])
        return (min(lo, hi), max(lo, hi))

    val = _to_seconds(raw)
    return (val, val)


class PlaywrightTitleChecker(TitleChecker):
    """Check Naver unified search for duplicate titles using Playwright.

    Searches with the keyword-only query, then compares each result
    against the full title.

    Args:
        page:  An open Playwright Page (typically the same browser
               session used for blog posting).
        match: ``"exact"`` for full-title match, ``"contains"`` for
               substring match.
        delay: Delay DSL between search requests (e.g. ``"1s ~ 2s"``).
    """

    def __init__(
        self,
        page,
        *,
        match: str = "exact",
        delay: str = "1s ~ 2s",
    ) -> None:
        self._page = page
        self._match = match
        self._delay = _parse_delay(delay)

    @override
    def is_duplicate(self, title: str, query: str) -> bool:
        """Search Naver for *query*, return True if *title* is in results."""
        lo, hi = self._delay
        time.sleep(random.uniform(lo, hi))

        encoded = urllib.parse.quote_plus(query)
        url = f"{_NAVER_SEARCH}?query={encoded}"

        self._page.goto(url)
        self._page.wait_for_load_state("domcontentloaded")

        try:
            self._page.wait_for_selector(
                _TITLE_SELECTOR, state="attached", timeout=5_000,
            )
        except Exception:
            logger.info("[title_check]     검색 결과 없음 → 중복 아님")
            return False

        normalized_title = _normalize(title)

        elements = self._page.query_selector_all(_TITLE_SELECTOR)
        logger.info("[title_check]     검색 결과 %d건 확인 중...", len(elements))

        for el in elements:
            # inner_text() strips <mark> tags automatically.
            result_title = _normalize(el.inner_text())

            if self._match == "contains":
                if normalized_title in result_title:
                    logger.info("[title_check]     중복 발견 (contains): %r", el.inner_text().strip())
                    return True
            else:  # exact
                if result_title == normalized_title:
                    logger.info("[title_check]     중복 발견 (exact): %r", el.inner_text().strip())
                    return True

        logger.info("[title_check]     일치 항목 없음 → 중복 아님")
        return False
