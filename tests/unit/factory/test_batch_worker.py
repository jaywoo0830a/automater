"""
tests/unit/factory/test_batch_worker.py
-------------------------------------
BatchWorker — executes a batch of PostingSpecs through BlogEditor.

Uses RecordingEditor (no browser) + StubTextGenerator + NoopImageProcessor.
No Playwright, no Gemini, no real DB session needed for unit-style tests.
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
from automator.options import AccountOption

from factory.batch_worker import BatchWorker, ItemResult


# ---------------------------------------------------------------------------
# RecordingEditor — captures calls without a browser
# ---------------------------------------------------------------------------

class RecordingEditor(BlogEditor):
    def __init__(self, dry_run=True):
        super().__init__(dry_run=dry_run)
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

    def insert_link(self, url):
        self.calls.append(("insert_link", url))

    def move_cursor(self, position="end"):
        self.calls.append(("cursor", position))

    def publish(self):
        self.calls.append(("publish",))


# ---------------------------------------------------------------------------
# Fakes — lightweight DB model replacements
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))


def _account_row(username="testuser", blog_id="testblog"):
    return SimpleNamespace(
        id=1,
        username=username,
        password_enc="pw",
        extra={"blog_id": blog_id},
        last_used_at=None,
    )


def _keyword(slug, value, cat_id=1):
    return SimpleNamespace(
        id=0, category=SimpleNamespace(slug=slug, id=cat_id),
        value=value, affixes=[],
    )


def _combination(combo_id, keywords, campaign):
    return SimpleNamespace(
        id=combo_id,
        campaign=campaign,
        keywords=keywords,
    )


def _batch_item(item_id, combination):
    return SimpleNamespace(
        id=item_id,
        combination=combination,
        status="pending",
        result_url=None,
        error_message=None,
        completed_at=None,
    )


def _batch(batch_id, items, account, scheduled_at=None):
    return SimpleNamespace(
        id=batch_id,
        account=account,
        items=items,
        scheduled_at=scheduled_at or (datetime.now(tz=KST) + timedelta(hours=2)),
        status="pending",
        started_at=None,
        completed_at=None,
        worker_pid=None,
    )


def _campaign():
    return SimpleNamespace(
        layout=None,
        publish_preset=None,
        run_preset=None,
        affix_overrides=[],
        tokens=[SimpleNamespace(slug="region", token_type="keyword", value=None, sort_order=0)],
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
def recording_editor():
    return RecordingEditor()


@pytest.fixture
def editor_factory(recording_editor):
    """Factory that always returns the same RecordingEditor."""
    def factory(account):
        return recording_editor
    return factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchWorker:

    def test_processes_all_items(self, runner, editor_factory):
        campaign = _campaign()
        account = _account_row()
        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원", 1)], campaign)),
        ]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        results = worker.run_batch(batch)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert all(r.error is None for r in results)

    def test_item_status_updated_to_completed(self, runner, editor_factory):
        campaign = _campaign()
        account = _account_row()
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        worker.run_batch(batch)

        assert items[0].status == "completed"
        assert items[0].completed_at is not None

    def test_batch_status_transitions(self, runner, editor_factory):
        campaign = _campaign()
        account = _account_row()
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        worker.run_batch(batch)

        assert batch.status == "completed"
        assert batch.started_at is not None
        assert batch.completed_at is not None

    def test_failed_item_does_not_stop_batch(self, runner, editor_factory):
        """One failing item should not prevent others from executing."""
        campaign = _campaign()
        account = _account_row()

        # First item will fail because account has empty username
        bad_combo = _combination(
            101,
            [_keyword("region", "강남", 1)],
            campaign,
        )
        good_combo = _combination(
            102,
            [_keyword("region", "수원", 1)],
            campaign,
        )

        # Sabotage the editor for first call only
        call_count = {"n": 0}
        original_factory = editor_factory

        def failing_then_ok(account):
            call_count["n"] += 1
            editor = RecordingEditor()
            if call_count["n"] == 1:
                def exploding_open():
                    raise RuntimeError("Browser crashed")
                editor.open = exploding_open
            return editor

        items = [_batch_item(1, bad_combo), _batch_item(2, good_combo)]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=failing_then_ok)
        results = worker.run_batch(batch)

        assert results[0].success is False
        assert "Browser crashed" in results[0].error
        assert items[0].status == "failed"
        assert "Browser crashed" in items[0].error_message

        assert results[1].success is True
        assert items[1].status == "completed"

    def test_batch_with_all_failures_marked_failed(self, runner):
        campaign = _campaign()
        account = _account_row()

        def always_fail(acc):
            editor = RecordingEditor()
            def boom():
                raise RuntimeError("dead")
            editor.open = boom
            return editor

        items = [
            _batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign)),
            _batch_item(2, _combination(102, [_keyword("region", "수원", 1)], campaign)),
        ]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=always_fail)
        worker.run_batch(batch)

        assert batch.status == "failed"
        assert all(item.status == "failed" for item in items)

    def test_editor_receives_correct_account(self, runner):
        """editor_factory is called with the batch's account."""
        campaign = _campaign()
        account = _account_row(username="myuser", blog_id="myblog")
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        received_accounts = []

        def capturing_factory(acc):
            received_accounts.append(acc)
            return RecordingEditor()

        worker = BatchWorker(runner=runner, editor_factory=capturing_factory)
        worker.run_batch(batch)

        assert len(received_accounts) == 1
        assert received_accounts[0].username == "myuser"

    def test_editor_calls_publish(self, runner, editor_factory, recording_editor):
        campaign = _campaign()
        account = _account_row()
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        worker.run_batch(batch)

        actions = [c[0] for c in recording_editor.calls]
        assert "open" in actions
        assert "title" in actions
        assert "publish" in actions

    def test_media_resolver_passed_through(self, runner, editor_factory):
        """media_resolver is forwarded to build_posting_spec."""
        resolved = []

        def tracking_resolver(media_id):
            resolved.append(media_id)
            return f"/uploads/{media_id}/file.jpg"

        campaign = _campaign()
        campaign.layout = SimpleNamespace(slots=[
            SimpleNamespace(sort_order=0, block_type="image", config={"media_id": 42}),
        ])
        account = _account_row()
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        worker = BatchWorker(
            runner=runner,
            editor_factory=editor_factory,
            media_resolver=tracking_resolver,
        )
        worker.run_batch(batch)

        assert 42 in resolved

    def test_returns_item_results(self, runner, editor_factory):
        campaign = _campaign()
        account = _account_row()
        items = [_batch_item(1, _combination(101, [_keyword("region", "강남", 1)], campaign))]
        batch = _batch(10, items, account)

        worker = BatchWorker(runner=runner, editor_factory=editor_factory)
        results = worker.run_batch(batch)

        assert len(results) == 1
        assert isinstance(results[0], ItemResult)
        assert results[0].item_id == 1
        assert results[0].success is True
