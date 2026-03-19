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
        db_url="mysql+pymysql://...",
        workers=5,
        dry_run=True,
    )
    result = runner.run()
    print(result)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool, current_process

from sqlalchemy import select, func

KST = timezone(timedelta(hours=9))


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
    """Claim and execute one pending batch."""
    from factory.db import get_engine
    from sqlalchemy.orm import Session
    from factory.models import Batch, BatchItem, Combination, Keyword
    from factory.logging_config import setup, get_logger
    from automator.job import PostingJob
    from automator.options import AccountOption, TitleOption, ParagraphBlock, PublishOption, RunSetting, Section
    from playwright.sync_api import sync_playwright

    setup(log_dir=args.get("log_dir", "logs"))

    db_url  = args["db_url"]
    dry_run = args["dry_run"]
    pid     = current_process().pid
    now     = datetime.now(tz=KST)

    log = get_logger(__name__)
    result = {"items_done": 0, "items_failed": 0,
              "batch_done": False, "batch_failed": False}

    engine = get_engine(db_url)
    with Session(engine) as session, session.begin():
        # Claim one pending batch (ORDER BY scheduled_at ASC, LIMIT 1)
        batch = (
            session.query(Batch)
            .filter_by(status="pending")
            .order_by(Batch.scheduled_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if not batch:
            return result

        batch.status     = "running"
        batch.worker_pid = pid
        batch.started_at = now
        session.flush()

        batch_id     = batch.id
        scheduled_at = batch.scheduled_at
        items        = session.query(BatchItem).filter_by(batch_id=batch_id, status="pending").all()

        log = get_logger(__name__, batch_id=batch_id)
        log.info("batch claimed — %d items, scheduled_at=%s", len(items), scheduled_at)

        if not items:
            batch.status       = "done"
            batch.completed_at = now
            result["batch_done"] = True
            log.info("batch empty — marked done")
            return result

        # All items share the same account
        account     = batch.account
        account_opt = AccountOption(
            username     = account.username,
            password     = account.password_enc,
            meta         = account.extra or {},
            session_path = (account.extra or {}).get("session_path", "session_state.json"),
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, slow_mo=200)
                ctx     = browser.new_context(
                    storage_state=account_opt.resolved_session_path
                    if os.path.exists(account_opt.resolved_session_path)
                    else None,
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )

                for item in items:
                    page   = ctx.new_page()
                    combo  = item.combination
                    blog_id = (account.extra or {}).get("blog_id", "")

                    from automator.smart_editor import SmartEditorOne
                    editor = SmartEditorOne(
                        page,
                        f"https://blog.naver.com/{blog_id}?Redirect=Write&",
                        dry_run=dry_run,
                    )
                    try:
                        title_opt   = _build_title_option(combo)
                        body_blocks = _build_body(combo)
                        publish_opt = PublishOption(
                            mode="fixed",
                            at=(
                                scheduled_at.replace(tzinfo=KST)
                                if scheduled_at.tzinfo is None
                                else scheduled_at
                            ),
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
                        item.status       = "done"
                        item.completed_at = now
                        result["items_done"] += 1
                        log.info("item %s done", item.id)
                    except Exception as e:
                        item.status        = "failed"
                        item.error_message = str(e)[:512]
                        result["items_failed"] += 1
                        log.exception("item %s failed: %s", item.id, e)
                    finally:
                        page.close()

                ctx.storage_state(path=account_opt.resolved_session_path)
                browser.close()

            final_status         = "done" if result["items_failed"] == 0 else "failed"
            batch.status         = final_status
            batch.completed_at   = now
            result["batch_done"]   = final_status == "done"
            result["batch_failed"] = final_status == "failed"

        except Exception as e:
            batch.status         = "failed"
            batch.completed_at   = now
            result["batch_failed"] = True
            log.exception("batch failed unexpectedly: %s", e)

    return result


def _build_values(combo: "Combination") -> dict[str, str]:
    """Build slug → value dict from combination's keywords."""
    has_suffix = bool((combo.config or {}).get("has_suffix", 1))
    values = {}
    for kw in sorted(combo.keywords, key=lambda k: k.category.sort_order if hasattr(k.category, "sort_order") else 0):
        slug        = kw.category.slug
        full_val    = kw.value
        display_val = kw.display_value
        values[slug] = full_val if (has_suffix or not display_val) else display_val
    return values


def _build_title_option(combo):
    from automator.options import TitleOption
    campaign = combo.campaign
    return TitleOption(
        template=campaign.title_template,
        values=_build_values(combo),
    )


def _build_body(combo):
    from automator.options import ParagraphBlock, Section
    values  = _build_values(combo)
    keyword = " ".join(values.values())
    prompt  = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(ParagraphBlock(prompt=prompt) for _ in range(3)))]


# ---------------------------------------------------------------------------
# FactoryRunner
# ---------------------------------------------------------------------------

class FactoryRunner:
    """
    Runs all pending batches using a multiprocessing Pool.

    Args:
        db_url:  SQLAlchemy connection URL (mysql+pymysql://...).
        workers: Number of parallel browser processes.
        dry_run: If True, publish popover opens but confirm is skipped.
    """

    def __init__(self, db_url: str, workers: int = 5, dry_run: bool = False) -> None:
        self._db_url  = db_url
        self._workers = workers
        self._dry_run = dry_run

    def run(self) -> RunResult:
        """Dispatch workers until no pending batches remain."""
        from factory.db import get_engine
        from sqlalchemy.orm import Session
        from factory.models import Batch

        engine = get_engine(self._db_url)
        with Session(engine) as session, session.begin():
            pending = session.query(func.count(Batch.id)).filter_by(status="pending").scalar() or 0

        if pending == 0:
            return RunResult()

        total = RunResult()
        worker_args = [
            {"db_url": self._db_url, "dry_run": self._dry_run}
            for _ in range(pending)
        ]

        with Pool(processes=min(self._workers, pending)) as pool:
            for r in pool.map(_worker, worker_args):
                total.batches_attempted += 1
                total.batches_done      += int(r["batch_done"])
                total.batches_failed    += int(r["batch_failed"])
                total.items_done        += r["items_done"]
                total.items_failed      += r["items_failed"]

        return total
