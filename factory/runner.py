"""
factory/runner.py
------------------
Executes pending batches in parallel using multiprocessing.

Each worker process:
    1. Locks one batch (status = 'running', worker_pid = PID)
    2. Iterates batch_items and runs PostingJob for each
    3. Marks items done/failed, then batch done/failed

Usage:
    from factory.runner import FactoryRunner

    runner = FactoryRunner(
        db_config={...},    # passed to Database.from_config()
        workers=5,          # concurrent browser processes
        dry_run=True,       # True = don't actually publish
    )
    result = runner.run()
    print(result)
"""

from __future__ import annotations

import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool, current_process
from typing import Any

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_CLAIM_BATCH_SQL = """
    UPDATE batches
    SET    status = 'running',
           worker_pid = %s,
           started_at = %s
    WHERE  status = 'pending'
    ORDER  BY scheduled_at ASC
    LIMIT  1
"""

_FETCH_CLAIMED_BATCH_SQL = """
    SELECT id, account_id, scheduled_at
    FROM   batches
    WHERE  status = 'running'
      AND  worker_pid = %s
    LIMIT  1
"""

_FETCH_BATCH_ITEMS_SQL = """
    SELECT bi.id, bi.combination_id,
           c.spacing_rule_id, c.config  AS combo_config,
           camp.title_template,
           a.naver_id, a.naver_pw, a.blog_id, a.session_path, a.proxy
    FROM   batch_items  bi
    JOIN   combinations c    ON c.id    = bi.combination_id
    JOIN   campaigns    camp ON camp.id = c.campaign_id
    JOIN   batches      b    ON b.id    = bi.batch_id
    JOIN   accounts     a    ON a.id    = b.account_id
    WHERE  bi.batch_id = %s
      AND  bi.status   = 'pending'
"""

_FETCH_COMBO_KEYWORDS_SQL = """
    SELECT kc.slug, kc.sort_order, k.value, k.display_value
    FROM   combination_keywords ck
    JOIN   keywords             k  ON k.id  = ck.keyword_id
    JOIN   keyword_categories   kc ON kc.id = k.category_id
    WHERE  ck.combination_id = %s
    ORDER BY kc.sort_order
"""

_MARK_ITEM_DONE_SQL = """
    UPDATE batch_items
    SET    status = 'done', post_url = %s, published_at = %s
    WHERE  id = %s
"""

_MARK_ITEM_FAILED_SQL = """
    UPDATE batch_items
    SET    status = 'failed', error_message = %s
    WHERE  id = %s
"""

_MARK_BATCH_DONE_SQL = """
    UPDATE batches
    SET    status = %s, completed_at = %s
    WHERE  id = %s
"""

_RESET_ACCOUNT_STATUS_SQL = """
    UPDATE accounts SET status = 'cooling' WHERE id = %s
"""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    batches_attempted: int = 0
    batches_done:      int = 0
    batches_failed:    int = 0
    items_done:        int = 0
    items_failed:      int = 0

    def __str__(self) -> str:
        return (
            f"RunResult("
            f"batches={self.batches_done}/{self.batches_attempted}, "
            f"items={self.items_done} done / {self.items_failed} failed)"
        )


# ---------------------------------------------------------------------------
# Worker function (runs in child process)
# ---------------------------------------------------------------------------

def _worker(args: dict) -> dict:
    """
    Claim and execute one pending batch.
    Returns a dict with counts for the parent to aggregate.
    """
    from factory.db import Database
    from factory.logging_config import setup, get_logger
    from automator.job import PostingJob
    from automator.options import (
        AccountOption, TitleOption, TextBlock, PublishOption, RunSetting, KST
    )
    from automator.smart_editor import SmartEditorOne
    from playwright.sync_api import sync_playwright

    # Initialize logging in this child process
    setup(log_dir=args.get("log_dir", "logs"))

    db_config = args["db_config"]
    dry_run   = args["dry_run"]
    pid       = current_process().pid
    now       = datetime.now(tz=KST)

    # Base logger before batch_id is known
    log = get_logger(__name__)
    result = {"items_done": 0, "items_failed": 0,
              "batch_done": False, "batch_failed": False}

    with Database.from_config(**db_config) as db:
        # Claim one batch
        db.execute(_CLAIM_BATCH_SQL, (pid, now))
        batch = db.fetch_one(_FETCH_CLAIMED_BATCH_SQL, (pid,))
        if not batch:
            return result  # no batch available for this worker

        batch_id     = batch["id"]
        scheduled_at = batch["scheduled_at"]
        items        = db.fetch_all(_FETCH_BATCH_ITEMS_SQL, (batch_id,))

        # Re-bind logger with batch_id so every line includes it
        log = get_logger(__name__, batch_id=batch_id)
        log.info("batch claimed — %d items, scheduled_at=%s", len(items), scheduled_at)

        if not items:
            db.execute(_MARK_BATCH_DONE_SQL, ("done", now, batch_id))
            result["batch_done"] = True
            log.info("batch empty — marked done")
            return result

        # All items share the same account (enforced by dispatcher)
        first        = items[0]
        account_opt  = AccountOption(
            username     = first["naver_id"],
            password     = first["naver_pw"],
            meta         = {"blog_id": first["blog_id"]},
            session_path = first["session_path"] or "session_state.json",
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, slow_mo=200)
                ctx     = browser.new_context(
                    storage_state=account_opt.resolved_session_path
                    if os.path.exists(account_opt.resolved_session_path)
                    else None,
                    locale      = "ko-KR",
                    timezone_id = "Asia/Seoul",
                )

                for item in items:
                    page   = ctx.new_page()
                    editor = SmartEditorOne(
                        page,
                        f"https://blog.naver.com/{first['blog_id']}?Redirect=Write&",
                        dry_run=dry_run,
                    )
                    try:
                        dim_values  = db.fetch_all(
                            _FETCH_COMBO_KEYWORDS_SQL, (item["combination_id"],)
                        )
                        title_opt   = _build_title_option(item, dim_values)
                        body_blocks = _build_body(item, dim_values)
                        publish_opt = PublishOption(
                            mode = "fixed",
                            at   = scheduled_at.replace(tzinfo=KST)
                                   if scheduled_at.tzinfo is None
                                   else scheduled_at,
                        )
                        job = (
                            PostingJob
                            .for_account(account_opt)
                            .with_title(title_opt)
                            .with_body(body_blocks)
                            .with_publish(publish_opt)
                            .with_setting(RunSetting())
                        )
                        job.run(editor)
                        db.execute(_MARK_ITEM_DONE_SQL, (None, now, item["id"]))
                        result["items_done"] += 1
                        log.info("item %s done", item["id"])
                    except Exception as e:
                        error_msg = str(e)[:512]
                        db.execute(_MARK_ITEM_FAILED_SQL, (error_msg, item["id"]))
                        result["items_failed"] += 1
                        log.exception("item %s failed: %s", item["id"], error_msg)
                    finally:
                        page.close()

                ctx.storage_state(path=account_opt.resolved_session_path)
                browser.close()

            final_status = "done" if result["items_failed"] == 0 else "failed"
            db.execute(_MARK_BATCH_DONE_SQL, (final_status, now, batch_id))
            result["batch_done"]   = final_status == "done"
            result["batch_failed"] = final_status == "failed"
            log.info(
                "batch %s — %d done / %d failed",
                final_status, result["items_done"], result["items_failed"],
            )

        except Exception as e:
            db.execute(_MARK_BATCH_DONE_SQL, ("failed", now, batch_id))
            result["batch_failed"] = True
            log.exception("batch failed unexpectedly: %s", e)

    return result


def _build_values(item: dict, combo_keywords: list[dict]) -> dict[str, str]:
    """
    Build slug → value dict from combination's keywords.

    has_suffix (stored in combinations.config JSON) determines whether
    to use value ('강남구') or display_value ('강남').
    """
    import json as _json
    combo_config = _json.loads(item["combo_config"] or "{}")
    has_suffix   = bool(combo_config.get("has_suffix", 1))

    values = {}
    for kw in combo_keywords:
        slug        = kw["slug"]
        full_val    = kw["value"]
        display_val = kw["display_value"]
        values[slug] = full_val if (has_suffix or not display_val) else display_val
    return values


def _build_title_option(item: dict, combo_keywords: list[dict]):
    from automator.options import TitleOption
    return TitleOption(
        template = item["title_template"],
        values   = _build_values(item, combo_keywords),
    )


def _build_body(item: dict, combo_keywords: list[dict]):
    from automator.options import TextBlock
    values  = _build_values(item, combo_keywords)
    keyword = " ".join(values[slug] for slug in sorted(values))
    prompt  = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [
        TextBlock(prompt=prompt),
        TextBlock(prompt=prompt),
        TextBlock(prompt=prompt),
    ]


# ---------------------------------------------------------------------------
# FactoryRunner
# ---------------------------------------------------------------------------

class FactoryRunner:
    """
    Runs all pending batches using a multiprocessing Pool.

    Args:
        db_config: kwargs for Database.from_config() passed to each worker.
        workers:   Number of parallel browser processes.
        dry_run:   If True, publish popover opens but confirm is skipped.
    """

    def __init__(
        self,
        db_config: dict,
        workers:   int  = 5,
        dry_run:   bool = False,
    ) -> None:
        self._db_config = db_config
        self._workers   = workers
        self._dry_run   = dry_run

    def run(self) -> RunResult:
        """
        Dispatch workers until no pending batches remain.
        Each worker claims and processes exactly one batch.
        """
        from factory.db import Database

        # Count pending batches to know how many workers to spawn
        with Database.from_config(**self._db_config) as db:
            row = db.fetch_one(
                "SELECT COUNT(*) AS cnt FROM batches WHERE status = 'pending'"
            )
            pending = row["cnt"] if row else 0

        if pending == 0:
            return RunResult()

        total = RunResult()
        args  = [
            {"db_config": self._db_config, "dry_run": self._dry_run}
            for _ in range(pending)
        ]

        with Pool(processes=min(self._workers, pending)) as pool:
            for r in pool.map(_worker, args):
                total.batches_attempted += 1
                total.batches_done      += int(r["batch_done"])
                total.batches_failed    += int(r["batch_failed"])
                total.items_done        += r["items_done"]
                total.items_failed      += r["items_failed"]

        return total
