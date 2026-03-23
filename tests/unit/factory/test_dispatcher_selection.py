"""
tests/unit/factory/test_dispatcher_selection.py
-------------------------------------------------
Unit tests for BatchDispatcher account selection and campaign filtering.

These test the new parameters without a real DB — uses simple fakes.
Integration tests in tests/integration/ cover the full DB path.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from factory.dispatcher import (
    BatchDispatcher,
    DispatchResult,
    filter_accounts_by_ids,
    filter_accounts_by_availability,
    BATCH_SIZE,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 3, 23, 14, 0, tzinfo=KST)
SCHEDULE_BASE = datetime(2026, 3, 23, 15, 0, tzinfo=KST)


def _fake_account(
    id: int,
    username: str = "user",
    status: str = "active",
    last_used_at: datetime | None = None,
    cooldown_days: int = 14,
) -> MagicMock:
    acc = MagicMock()
    acc.id = id
    acc.username = f"{username}_{id}"
    acc.status = status
    acc.last_used_at = last_used_at
    acc.cooldown_days = cooldown_days
    return acc


# ---------------------------------------------------------------------------
# filter_accounts_by_ids — new pure function
# ---------------------------------------------------------------------------

class TestFilterAccountsByIds:

    def test_returns_all_when_ids_is_none(self):
        accounts = [_fake_account(1), _fake_account(2), _fake_account(3)]
        result = filter_accounts_by_ids(accounts, account_ids=None)
        assert len(result) == 3

    def test_filters_to_specified_ids(self):
        accounts = [_fake_account(1), _fake_account(2), _fake_account(3)]
        result = filter_accounts_by_ids(accounts, account_ids=[1, 3])
        assert [a.id for a in result] == [1, 3]

    def test_preserves_order_of_input_ids(self):
        accounts = [_fake_account(1), _fake_account(2), _fake_account(3)]
        result = filter_accounts_by_ids(accounts, account_ids=[3, 1])
        assert [a.id for a in result] == [3, 1]

    def test_ignores_ids_not_in_accounts(self):
        accounts = [_fake_account(1), _fake_account(2)]
        result = filter_accounts_by_ids(accounts, account_ids=[1, 99])
        assert [a.id for a in result] == [1]

    def test_empty_ids_returns_empty(self):
        accounts = [_fake_account(1)]
        result = filter_accounts_by_ids(accounts, account_ids=[])
        assert result == []


# ---------------------------------------------------------------------------
# filter_accounts_by_availability — extracted pure function
# ---------------------------------------------------------------------------

class TestFilterAccountsByAvailability:

    def test_never_used_is_available(self):
        accounts = [_fake_account(1, last_used_at=None)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 1

    def test_within_cooldown_is_excluded(self):
        used_5_days_ago = NOW - timedelta(days=5)
        accounts = [_fake_account(1, last_used_at=used_5_days_ago, cooldown_days=14)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 0

    def test_past_cooldown_is_available(self):
        used_15_days_ago = NOW - timedelta(days=15)
        accounts = [_fake_account(1, last_used_at=used_15_days_ago, cooldown_days=14)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 1

    def test_inactive_account_excluded(self):
        accounts = [_fake_account(1, status="disabled", last_used_at=None)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 0

    def test_cooling_account_excluded(self):
        accounts = [_fake_account(1, status="cooling", last_used_at=None)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 0

    def test_mixed_availability(self):
        accounts = [
            _fake_account(1, last_used_at=None),
            _fake_account(2, last_used_at=NOW - timedelta(days=5)),
            _fake_account(3, last_used_at=NOW - timedelta(days=20)),
            _fake_account(4, status="disabled"),
        ]
        result = filter_accounts_by_availability(accounts, NOW)
        assert [a.id for a in result] == [1, 3]

    def test_naive_datetime_treated_as_kst(self):
        naive_15_days_ago = (NOW - timedelta(days=15)).replace(tzinfo=None)
        accounts = [_fake_account(1, last_used_at=naive_15_days_ago, cooldown_days=14)]
        result = filter_accounts_by_availability(accounts, NOW)
        assert len(result) == 1
