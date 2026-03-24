"""
tests/unit/factory/test_batch_stop_retry.py
---------------------------------------------
Tests for two new BatchWorker capabilities:

    #5  Stop  — cancel a running batch mid-execution
    #6  Retry — reset failed items and re-run them

Uses the same RecordingEditor + fake model pattern as test_batch_worker.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from automator.editor import BlogEditor
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.spec_validator import SpecValidator
from automator.content_builder import ContentBuilder
from automator.runner import JobRunner

from factory.batch_worker import (
    BatchWorker,
    CancellationToken,
    ItemResult,
    retry_failed_items,
)


# ---------------------------------------------------------------------------
# RecordingEditor
# ---------------------------------------------------------------------------

class RecordingEditor(BlogEditor):
    def __init__(self):
        self.calls: list[tuple] = []

    def open(self):
        self.calls.append(("open",))

    def write_title(self, title):
        self.calls.append(("title", title))

    def insert_text(self, text, newlines=2):
        self.calls.append(("insert_text", text, newlines))

    def insert_heading(self, text, level=2):
        self.calls.append(("insert_heading", text, level))

    def insert_quote(self, text):
        self.calls.append(("insert_quote", text))

    def insert_divider(self):
        self.calls.append(("insert_divider",))

    def upload_file(self, path):
        self.calls.append(("upload_file", path))

    def move_cursor(self, position="end"):
        self.calls.append(("cursor", position))

    def set_representative_media(self, index):
        self.calls.append(("representative", index))

    def publish(self, schedule_at=None):
        self.calls.append(("publish", schedule_at))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))


def _account_row():
    return SimpleNamespace(
        id=1, username="testuser", password_enc="pw",
        extra={"blog_id": "testblog"}, last_used_at=None,
    )


def _keyword(slug, value, cat_id=1):
    return SimpleNamespace(
        id=0, category=SimpleNamespace(slug=slug, id=cat_id),
        value=value, affixes=[],
    )


def _combination(combo_id, keywords, campaign):
    return SimpleNamespace(id=combo_id, campaign=campaign, keywords=keywords)


def _batch_item(item_id, combination, status="pending"):
    return SimpleNamespace(
        id=item_id, combination=combination, status=status,
        result_url=None, error_message=None, completed_at=None,
    )


def _batch(batch_id, items, account, scheduled_at=None):
    return SimpleNamespace(
        id=batch_id, account=account, items=items,
        scheduled_at=scheduled_at or (datetime.now(tz=KST) + timedelta(hours=2)),
        status="pending", started_at=None, completed_at=None, worker_pid=None,
    )


def _campaign():
    return SimpleNamespace(
        layout=None, publish_preset=None, run_preset=None,
        affix_overrides=[],
        tokens=[SimpleNamespace(
            slug="region", token_type="keyword", value=None, sort_order=0,
        )],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return JobRunner(
        SpecValidator(),
        ContentBuilder(StubTextGenerator(), NoopImageProcessor()),
    )


@pytest.fixture
def editor_factory():
    def factory(account):
        return RecordingEditor()
    return factory


# ===========================================================================
# #5 — CancellationToken
# ===========================================================================

class TestCancellationToken:

    def test_starts_not_cancelled(self):
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_sets_flag(self):
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_cancel_is_idempotent(self):
        token = CancellationToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled is True


# ===========================================================================
# #5 — Stop (cancellation during run_batch)
# ===========================================================================

class TestBatchStop:

    def test_already_cancelled_token_skips_all_items(self, runner, editor_factory):
        """If token is cancelled before run_batch, no items are processed."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign)),
        ]
        batch = _batch(10, items, account)

        token = CancellationToken()
        token.cancel()

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        results = worker.run_batch(batch, cancel_token=token)

        assert results == []
        assert items[0].status == "cancelled"
        assert items[1].status == "cancelled"
        assert batch.status == "stopped"

    def test_cancel_mid_batch(self, runner):
        """Cancel after first item — second item should not execute."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign)),
            _batch_item(3, _combination(103, [_keyword("region", "분당")], campaign)),
        ]
        batch = _batch(10, items, account)

        token = CancellationToken()
        process_count = {"n": 0}

        def cancel_after_first(acc):
            process_count["n"] += 1
            if process_count["n"] == 1:
                token.cancel()
            return RecordingEditor()

        worker = BatchWorker(runner=runner, editor_factory=cancel_after_first)
        results = worker.run_batch(batch, cancel_token=token)

        # Only the first item was processed
        assert len(results) == 1
        assert results[0].success is True
        assert items[0].status == "completed"

        # Remaining items are cancelled
        assert items[1].status == "cancelled"
        assert items[2].status == "cancelled"

        assert batch.status == "stopped"

    def test_no_token_behaves_as_before(self, runner, editor_factory):
        """Without a token, run_batch works exactly as the original."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign)),
        ]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        results = worker.run_batch(batch)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert batch.status == "completed"

    def test_completed_items_preserved_after_stop(self, runner):
        """Items completed before cancellation stay completed."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign)),
        ]
        batch = _batch(10, items, account)

        token = CancellationToken()
        call_count = {"n": 0}

        def cancel_after_first(acc):
            call_count["n"] += 1
            if call_count["n"] == 1:
                token.cancel()
            return RecordingEditor()

        worker = BatchWorker(runner=runner, editor_factory=cancel_after_first)
        worker.run_batch(batch, cancel_token=token)

        assert items[0].status == "completed"
        assert items[0].completed_at is not None
        assert items[1].status == "cancelled"
        assert items[1].completed_at is None

    def test_stop_with_mixed_existing_statuses(self, runner, editor_factory):
        """Only pending items are cancelled. Already completed/failed stay."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="completed"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="failed"),
            _batch_item(3, _combination(103, [_keyword("region", "분당")], campaign), status="pending"),
        ]
        batch = _batch(10, items, account)

        token = CancellationToken()
        token.cancel()

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        worker.run_batch(batch, cancel_token=token)

        assert items[0].status == "completed"
        assert items[1].status == "failed"
        assert items[2].status == "cancelled"


# ===========================================================================
# #6 — Retry failed items
# ===========================================================================

class TestRetryFailedItems:

    def test_resets_failed_to_pending(self):
        campaign = _campaign()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="failed"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="failed"),
        ]
        items[0].error_message = "Browser crashed"
        items[0].completed_at = datetime.now(timezone.utc)
        items[1].error_message = "Timeout"
        items[1].completed_at = datetime.now(timezone.utc)

        batch = _batch(10, items, _account_row())
        batch.status = "failed"

        count = retry_failed_items(batch)

        assert count == 2
        assert items[0].status == "pending"
        assert items[0].error_message is None
        assert items[0].completed_at is None
        assert items[1].status == "pending"
        assert items[1].error_message is None

    def test_only_failed_items_are_reset(self):
        campaign = _campaign()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="completed"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="failed"),
            _batch_item(3, _combination(103, [_keyword("region", "분당")], campaign), status="pending"),
        ]
        items[1].error_message = "Timeout"
        items[1].completed_at = datetime.now(timezone.utc)

        batch = _batch(10, items, _account_row())
        count = retry_failed_items(batch)

        assert count == 1
        assert items[0].status == "completed"
        assert items[1].status == "pending"
        assert items[2].status == "pending"

    def test_resets_cancelled_items_too(self):
        campaign = _campaign()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="cancelled"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="failed"),
        ]
        batch = _batch(10, items, _account_row())
        count = retry_failed_items(batch)

        assert count == 2
        assert items[0].status == "pending"
        assert items[1].status == "pending"

    def test_batch_status_reset_to_pending(self):
        campaign = _campaign()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="failed"),
        ]
        items[0].error_message = "Error"
        items[0].completed_at = datetime.now(timezone.utc)

        batch = _batch(10, items, _account_row())
        batch.status = "failed"
        batch.completed_at = datetime.now(timezone.utc)

        retry_failed_items(batch)

        assert batch.status == "pending"
        assert batch.completed_at is None
        assert batch.started_at is None

    def test_no_failed_items_returns_zero(self):
        campaign = _campaign()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="completed"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="completed"),
        ]
        batch = _batch(10, items, _account_row())
        batch.status = "completed"

        count = retry_failed_items(batch)

        assert count == 0
        assert batch.status == "completed"

    def test_retry_then_run_processes_only_reset_items(self, runner, editor_factory):
        """End-to-end: retry resets items, then run_batch processes them."""
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남")], campaign), status="completed"),
            _batch_item(2, _combination(102, [_keyword("region", "수원")], campaign), status="failed"),
        ]
        items[1].error_message = "Timeout"
        items[1].completed_at = datetime.now(timezone.utc)

        batch = _batch(10, items, account)
        batch.status = "failed"

        retry_failed_items(batch)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        results = worker.run_batch(batch)

        # Only item 2 was re-processed (item 1 was already completed)
        assert len(results) == 1
        assert results[0].item_id == 2
        assert results[0].success is True
        assert items[1].status == "completed"
        assert batch.status == "completed"
