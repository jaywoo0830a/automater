"""Naver unified search rank extraction.

Searches Naver unified search (통합검색) for a keyword and checks
whether a post by *blog_id* appears in the result blocks (1-10위).

All interactions use real browser events (keyboard, mouse) to avoid
bot detection — no JS injection for navigation.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from automator.selector_loader import SelectorLoader

from observer.human import (
    human_click,
    human_delay,
    human_mouse_move,
    human_scroll,
)

logger = logging.getLogger(__name__)

_NAVER_URL = "https://www.naver.com"
_sel = SelectorLoader.load("selectors/naver/observer.yaml")

# Typing jitter (ms) — same range as session_manager.py
_TYPE_DELAY_MIN = 80
_TYPE_DELAY_MAX = 180


@dataclass
class SearchResult:
    """Result of searching for a blog post in Naver."""

    found: bool
    rank: int | None = None
    found_in: str | None = None  # unified
    result_url: str | None = None
    element: object = None  # the <a> element to click (not persisted)


NOT_FOUND = SearchResult(found=False)


class NaverSearcher:
    """Search Naver unified search for a keyword and locate a post by blog_id."""

    def __init__(self, page) -> None:
        self._page = page

    def search(self, keyword: str, blog_id: str) -> SearchResult:
        """Navigate to Naver, type keyword like a human, search, find rank."""
        # 1. Go to naver.com (like a real person opening a browser)
        self._page.goto(_NAVER_URL)
        self._page.wait_for_load_state("load")
        human_delay(1.0, 2.0)

        # 2. Click the search input
        search_input = self._page.locator("input#query")
        search_input.wait_for(state="visible", timeout=10_000)
        human_click(self._page, search_input)
        human_delay(0.3, 0.6)

        # 3. Type keyword character by character (real key events)
        avg_delay = random.randint(_TYPE_DELAY_MIN, _TYPE_DELAY_MAX)
        search_input.press_sequentially(keyword, delay=avg_delay)
        human_delay(0.3, 0.8)

        # 4. Press Enter to search (real keyboard event)
        self._page.keyboard.press("Enter")
        self._page.wait_for_load_state("load")
        human_delay(1.5, 2.5)

        # 5. Browse search results like a human, then find our post
        return self._browse_and_scan(blog_id)

    def _browse_and_scan(self, blog_id: str) -> SearchResult:
        """Browse search results with human-like scroll/dwell, scanning for blog_id."""
        css = _sel.css("unified_result_block")
        if not css:
            return NOT_FOUND

        try:
            self._page.wait_for_selector(css, state="attached", timeout=5_000)
        except Exception:
            logger.info("No search result blocks found")
            return NOT_FOUND

        vp = self._page.viewport_size or {"width": 1920, "height": 1080}
        content_height = self._page.evaluate("document.body.scrollHeight")

        # Human-like browsing of search results: scroll + mouse wander
        human_scroll(self._page, content_height, vp["height"])
        human_delay(1.0, 2.0)

        # Scroll back to top before scanning (a human re-checks from top)
        self._page.mouse.wheel(0, -content_height)
        human_delay(1.0, 1.5)

        # Now scan result blocks for our blog_id
        blocks = self._page.query_selector_all(css)
        found_result = NOT_FOUND

        for idx, block in enumerate(blocks, start=1):
            # Hover over each result briefly like a person reading
            try:
                block.scroll_into_view_if_needed()
                box = block.bounding_box()
                if box:
                    human_mouse_move(
                        self._page,
                        int(box["x"] + box["width"] * random.uniform(0.2, 0.8)),
                        int(box["y"] + box["height"] * random.uniform(0.3, 0.7)),
                    )
                    human_delay(0.5, 1.5)
            except Exception:
                pass

            links = block.query_selector_all("a[href]")
            for link in links:
                href = link.get_attribute("href") or ""
                if f"blog.naver.com/{blog_id}" in href:
                    logger.info("Found at rank %d in unified search", idx)
                    found_result = SearchResult(
                        found=True,
                        rank=idx,
                        found_in="unified",
                        result_url=href,
                        element=link,
                    )
                    # Don't return immediately — keep browsing a bit
                    # (a human doesn't click the very first match instantly)
                    remaining = blocks[idx:]
                    peek = random.randint(1, min(3, len(remaining) + 1))
                    for extra_block in remaining[:peek]:
                        try:
                            extra_block.scroll_into_view_if_needed()
                            ebox = extra_block.bounding_box()
                            if ebox:
                                human_mouse_move(
                                    self._page,
                                    int(ebox["x"] + ebox["width"] * random.uniform(0.2, 0.8)),
                                    int(ebox["y"] + ebox["height"] * random.uniform(0.3, 0.7)),
                                )
                                human_delay(0.3, 0.8)
                        except Exception:
                            pass
                    return found_result

        logger.info("Post not found for blog_id=%s", blog_id)
        return NOT_FOUND
