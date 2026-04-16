"""Post visit: human-like dwell and scroll behaviour."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime

from observer.human import _get_scroll_y, human_delay, human_mouse_move

logger = logging.getLogger(__name__)


@dataclass
class VisitData:
    """Metrics collected during a post visit."""

    scroll_pct: float
    dwell_seconds: float
    entered_at: datetime
    exited_at: datetime


class PostVisitor:
    """Dwell on a blog post with human-like patterns."""

    def __init__(self, page) -> None:
        self._page = page

    def visit_current_page(self) -> VisitData:
        """Dwell on the current page (already navigated via click)."""
        entered_at = datetime.utcnow()

        self._escape_iframe()

        vp = self._page.viewport_size or {"width": 1920, "height": 1080}

        # initial mouse movement
        human_mouse_move(
            self._page,
            random.randint(int(vp["width"] * 0.3), int(vp["width"] * 0.7)),
            random.randint(int(vp["height"] * 0.3), int(vp["height"] * 0.5)),
        )
        human_delay(0.5, 1.0)

        # Target: ~80% scroll over ~3 min dwell
        target_dwell = random.uniform(150.0, 210.0)
        target_scroll_pct = random.uniform(0.75, 0.85)

        scroll_pct = self._timed_scroll(vp, target_dwell, target_scroll_pct)

        exited_at = datetime.utcnow()

        return VisitData(
            scroll_pct=scroll_pct,
            dwell_seconds=(exited_at - entered_at).total_seconds(),
            entered_at=entered_at,
            exited_at=exited_at,
        )

    def _timed_scroll(
        self, vp: dict, target_dwell: float, target_scroll_pct: float,
    ) -> float:
        """Slowly scroll down over *target_dwell* seconds, reaching ~target_scroll_pct.

        Distributes wheel events across the dwell time with reading
        pauses and mouse wandering mixed in.
        """
        start = time.monotonic()
        max_y = self._get_max_scroll()
        if max_y <= 0:
            # page not scrollable — just idle
            self._idle(vp, target_dwell, start)
            return 0.0

        target_y = int(max_y * target_scroll_pct)
        logger.debug(
            "Timed scroll: target %d px (%.0f%%) over %.0fs",
            target_y, target_scroll_pct * 100, target_dwell,
        )

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= target_dwell:
                break

            current_y = _get_scroll_y(self._page)
            remaining_time = target_dwell - elapsed
            remaining_px = target_y - current_y

            if remaining_px <= 0:
                # reached target scroll — idle for rest of dwell
                self._idle(vp, remaining_time, time.monotonic())
                break

            # scroll a small amount
            amount = random.randint(100, 300)
            self._page.mouse.wheel(0, amount)
            time.sleep(random.uniform(0.05, 0.1))

            # reading pause — proportional to remaining time
            pause = remaining_time / max(1, remaining_px / 200)
            pause = min(pause, random.uniform(2.0, 5.0))
            pause = max(pause, random.uniform(0.5, 1.0))
            time.sleep(pause)

            # mouse wander sometimes
            if random.random() < 0.3:
                human_mouse_move(
                    self._page,
                    random.randint(int(vp["width"] * 0.1), int(vp["width"] * 0.9)),
                    random.randint(int(vp["height"] * 0.2), int(vp["height"] * 0.8)),
                )

            # occasional scroll-back
            if random.random() < 0.05:
                self._page.mouse.wheel(0, random.randint(-100, -30))
                time.sleep(random.uniform(0.3, 0.6))

        final_y = _get_scroll_y(self._page)
        result = min(final_y / max_y, 1.0) if max_y > 0 else 1.0
        logger.debug("Timed scroll done: %d px (%.0f%%)", final_y, result * 100)
        return result

    def _idle(self, vp: dict, duration: float, start: float) -> None:
        """Idle with mouse wander and occasional small scrolls."""
        while time.monotonic() - start < duration:
            chunk = min(duration - (time.monotonic() - start), random.uniform(3.0, 8.0))
            if chunk <= 0:
                break
            time.sleep(chunk)
            if random.random() < 0.5:
                human_mouse_move(
                    self._page,
                    random.randint(int(vp["width"] * 0.1), int(vp["width"] * 0.9)),
                    random.randint(int(vp["height"] * 0.2), int(vp["height"] * 0.8)),
                )
            if random.random() < 0.3:
                self._page.mouse.wheel(0, random.randint(-80, 100))

    def _get_max_scroll(self) -> int:
        """Get max scrollable distance, waiting for content to load."""
        for _ in range(20):
            try:
                max_y = self._page.evaluate(
                    "Math.max(document.body.scrollHeight,"
                    " document.documentElement.scrollHeight)"
                    " - (window.innerHeight || document.documentElement.clientHeight)",
                )
                if max_y > 100:
                    return max_y
            except Exception:
                pass
            time.sleep(0.5)
        logger.warning("Could not determine max scroll height")
        return 0

    def _escape_iframe(self) -> None:
        """If the blog post is inside an iframe, navigate to the iframe src directly."""
        try:
            iframe_src = self._page.evaluate(
                "(() => { const f = document.querySelector('iframe');"
                " return f ? f.src : null; })()",
            )
            if iframe_src:
                logger.debug("Navigating into iframe: %s", iframe_src[:80])
                self._page.goto(iframe_src)
                self._page.wait_for_load_state("load")
                human_delay(1.0, 2.0)
        except Exception:
            logger.debug("No iframe found, staying on current page")
