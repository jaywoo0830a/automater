"""One observation session: browser launch -> search -> visit -> close."""

from __future__ import annotations

import logging
import os
import random
from typing import Any

from automator.browser import build_context
from automator.models.campaign import Campaign
from automator.models.observation import Observation
from automator.stealth import DEFAULT_FINGERPRINT

from observer.collector import collect_session_ip, generate_random_fingerprint
from observer.human import human_click_element, human_delay
from observer.searcher import NaverSearcher
from observer.visitor import PostVisitor

logger = logging.getLogger(__name__)


class ObserverSession:
    """One browser session = one keyword observation.

    Each session gets a unique fingerprint (viewport, UA) so successive
    observations look like different visitors.
    """

    def __init__(
        self,
        pw,
        *,
        fingerprint_cfg: dict[str, Any] | None = None,
        headless: bool = True,
        display: str | None = None,
    ) -> None:
        self._pw = pw
        self._fp = fingerprint_cfg or generate_random_fingerprint()
        self._headless = headless
        self._display = display

    def execute(self, campaign: Campaign) -> Observation:
        """Run the full observation flow and return an unsaved Observation."""
        # Set DISPLAY so Playwright opens in the correct Xvfb
        old_display = os.environ.get("DISPLAY")
        if self._display:
            os.environ["DISPLAY"] = self._display

        try:
            return self._run(campaign)
        finally:
            if old_display is not None:
                os.environ["DISPLAY"] = old_display
            elif self._display and "DISPLAY" in os.environ:
                del os.environ["DISPLAY"]

    def _run(self, campaign: Campaign) -> Observation:
        browser_config = {
            "viewport": [self._fp["viewport_width"], self._fp["viewport_height"]],
            "user_agent": self._fp["user_agent"],
            "locale": "ko-KR",
            "timezone": "Asia/Seoul",
            "fingerprint": dict(DEFAULT_FINGERPRINT),
        }

        browser = self._pw.chromium.launch(headless=self._headless)
        ctx = build_context(browser, browser_config)
        page = ctx.new_page()

        try:
            session_ip = collect_session_ip(page)

            searcher = NaverSearcher(page)
            result = searcher.search(campaign.keyword, campaign.blog_id)

            obs = Observation(
                campaign_id=campaign.id,
                rank=result.rank,
                found_in=result.found_in,
                post_url=result.result_url,
                session_ip=session_ip,
                fingerprint=self._fp["hash"],
                user_agent=self._fp["user_agent"],
                viewport_width=self._fp["viewport_width"],
                viewport_height=self._fp["viewport_height"],
            )

            if result.found and result.element:
                human_delay(0.5, 1.0)

                with ctx.expect_page() as new_page_info:
                    human_click_element(page, result.element)

                blog_page = new_page_info.value
                blog_page.wait_for_load_state("load")
                human_delay(1.0, 2.0)

                visitor = PostVisitor(blog_page)
                vd = visitor.visit_current_page()
                obs.scroll_pct = vd.scroll_pct
                obs.dwell_seconds = vd.dwell_seconds
                obs.entered_at = vd.entered_at
                obs.exited_at = vd.exited_at

                human_delay(0.5, 1.0)
                blog_page.close()

                human_delay(1.5, 3.0)
                page.mouse.wheel(0, random.randint(100, 300))
                human_delay(1.0, 2.0)

            return obs
        finally:
            ctx.close()
            browser.close()
