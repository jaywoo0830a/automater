"""Observer daemon: polls MySQL for due schedules and runs sessions."""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from observer.collector import generate_random_fingerprint
from observer.session import ObserverSession
from observer.store import ObserverStore
from observer.vnc import start_vnc, stop_vnc

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WORKERS = 4


class ObserverDaemon:
    """Long-running process that observes Naver search rankings.

    Polls the database every *poll_interval* seconds for schedules
    whose ``scheduled_at`` has passed and processes them in parallel.
    Each worker gets its own VNC display for remote viewing.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._store = ObserverStore(config["mysql_url"])
        self._poll_interval: int = int(config.get("poll_interval", 30))
        self._headless: bool = config.get("headless", True)
        self._max_workers: int = int(
            config.get("max_workers", _DEFAULT_MAX_WORKERS),
        )

    def run(self) -> int:
        """Main daemon loop.  Never returns normally."""
        logger.info(
            "Observer daemon started (poll=%ds, headless=%s, workers=%d)",
            self._poll_interval,
            self._headless,
            self._max_workers,
        )
        self._store.create_tables()

        from observer.vnc_server import start_vnc_server
        start_vnc_server()

        while True:
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("Observer daemon stopped by user")
                return 0
            except Exception:
                logger.exception("Tick failed")

            time.sleep(self._poll_interval)

    def run_once(self) -> int:
        """Execute a single poll cycle (for testing / debugging)."""
        self._store.create_tables()
        self._tick()
        return 0

    def _tick(self) -> None:
        """One poll cycle: detect new campaigns, then process due schedules."""
        self._store.detect_new_campaigns()

        now = datetime.utcnow()
        schedules = self._store.fetch_due_schedules(now)
        if not schedules:
            logger.debug("No due schedules")
            return

        logger.info("Found %d due schedule(s), processing with %d workers",
                     len(schedules), self._max_workers)

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._process, idx, schedule): schedule
                for idx, schedule in enumerate(schedules)
            }
            for future in as_completed(futures):
                schedule = futures[future]
                try:
                    future.result()
                except Exception:
                    logger.exception("Schedule %d failed in thread", schedule.id)

    def _process(self, worker_id: int, schedule) -> None:
        """Process a single schedule with its own VNC display + browser."""
        from playwright.sync_api import sync_playwright

        campaign = schedule.campaign

        # Start VNC for this worker
        wv = start_vnc(worker_id)
        wv.schedule_id = schedule.id
        wv.keyword = campaign.keyword
        wv.blog_id = campaign.blog_id
        wv.status = "running"

        logger.info(
            "Processing schedule %d — keyword=%r, blog_id=%s (vnc ws://:%d)",
            schedule.id,
            campaign.keyword,
            campaign.blog_id,
            wv.ws_port,
        )

        pw = sync_playwright().start()
        try:
            fp = generate_random_fingerprint()
            session = ObserverSession(
                pw,
                fingerprint_cfg=fp,
                headless=False,
                display=wv.display,
            )
            observation = session.execute(campaign)
            self._store.save_observation(observation, schedule.id)

            logger.info(
                "Schedule %d done: rank=%s, found_in=%s",
                schedule.id,
                observation.rank,
                observation.found_in,
            )
        except Exception:
            logger.exception("Schedule %d failed", schedule.id)
            self._store.update_schedule_status(schedule.id, "skipped")
        finally:
            pw.stop()
            stop_vnc(wv)
