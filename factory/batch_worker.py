"""
factory/batch_worker.py
-------------------------
BatchWorker — executes a batch of PostingSpecs through BlogEditor.

Sits in the factory layer because it manages batch state transitions
(pending → running → completed/failed). All automator interaction goes
through contracts: PostingSpec, JobRunner, BlogEditor ABC.

Martin Ch.2 pattern: Worker depends on BlogEditor ABC, not SmartEditorOne.
The concrete editor is provided via editor_factory injection.

    worker = BatchWorker(
        runner=runner,
        editor_factory=lambda account: SmartEditorOne(page, write_url),
    )
    results = worker.run_batch(batch)

Testable: inject RecordingEditor + StubTextGenerator + NoopImageProcessor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from automator.contracts import PostingSpec
from automator.editor import BlogEditor
from automator.options import AccountOption
from automator.runner import JobRunner

from factory.job_builder import build_posting_spec


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

EditorFactory = Callable[[Any], BlogEditor]


@dataclass
class ItemResult:
    """Outcome of processing one BatchItem."""
    item_id: int
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# BatchWorker
# ---------------------------------------------------------------------------

class BatchWorker:
    """
    Execute all items in a batch through the posting pipeline.

    Dependencies (all injected):
        runner:         JobRunner — validate, build content, execute.
        editor_factory: Account row → BlogEditor. In production, creates
                        SmartEditorOne with Playwright. In tests, returns
                        RecordingEditor.
        media_resolver: Optional media_id → file path resolver.

    State management:
        Updates batch.status, batch.started_at, batch.completed_at.
        Updates item.status, item.error_message, item.completed_at.
        Does NOT call session.commit() — caller manages the session.
    """

    def __init__(
        self,
        runner: JobRunner,
        editor_factory: EditorFactory,
        media_resolver: Callable[[int], str] | None = None,
    ) -> None:
        self._runner = runner
        self._editor_factory = editor_factory
        self._media_resolver = media_resolver

    def run_batch(self, batch: Any) -> list[ItemResult]:
        """
        Process every pending item in the batch.

        Returns a list of ItemResult — one per item, in order.
        Failed items do not stop the batch. The batch is marked
        "completed" if any item succeeded, "failed" if all failed.
        """
        batch.status = "running"
        batch.started_at = datetime.now(timezone.utc)
        batch.worker_pid = os.getpid()

        results: list[ItemResult] = []
        success_count = 0

        for item in batch.items:
            if item.status != "pending":
                continue

            result = self._process_item(item, batch)
            results.append(result)
            if result.success:
                success_count += 1

        batch.completed_at = datetime.now(timezone.utc)
        batch.status = "completed" if success_count > 0 else "failed"

        return results

    def _process_item(self, item: Any, batch: Any) -> ItemResult:
        """Process one BatchItem. Never raises — catches all errors."""
        try:
            item.status = "running"

            account_opt = self._build_account_option(batch.account)
            spec = build_posting_spec(
                combo=item.combination,
                account_opt=account_opt,
                scheduled_at=batch.scheduled_at,
                media_resolver=self._media_resolver,
            )

            editor = self._editor_factory(batch.account)
            self._runner.run(spec, editor)

            item.status = "completed"
            item.completed_at = datetime.now(timezone.utc)
            return ItemResult(item_id=item.id, success=True)

        except Exception as exc:
            item.status = "failed"
            item.error_message = str(exc)
            item.completed_at = datetime.now(timezone.utc)
            return ItemResult(item_id=item.id, success=False, error=str(exc))

    @staticmethod
    def _build_account_option(account: Any) -> AccountOption:
        """Convert an Account DB row into an AccountOption value object."""
        return AccountOption(
            username=account.username,
            password=account.password_enc,
            meta=account.extra or {},
            session_path=f"{account.username}_session.json",
        )
