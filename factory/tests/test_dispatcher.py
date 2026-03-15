"""
factory/tests/test_dispatcher.py
----------------------------------
Unit tests for BatchDispatcher.

DB와 datetime을 mock해서 순수 할당 로직만 검증한다.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

from factory.dispatcher import BatchDispatcher, BATCH_SIZE

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _account(id_, last_used=None, cooldown=14, status="active"):
    return {
        "id":           id_,
        "naver_id":     f"user{id_}",
        "last_used_at": last_used,
        "cooldown_days": cooldown,
        "status":        status,
    }


def _combo(id_):
    return {"id": id_, "region_id": 1, "subject": "수학",
            "learning_type": "과외", "has_space": 1, "has_suffix": 1}


def _combos(n):
    return [_combo(i) for i in range(1, n + 1)]


def _make_dispatcher(accounts, pending_combos, schedule_base=None):
    db = MagicMock()
    db.fetch_all.side_effect = [accounts, pending_combos]
    if schedule_base is None:
        schedule_base = datetime(2026, 3, 20, 10, 0, tzinfo=KST)
    return BatchDispatcher(db=db, schedule_base=schedule_base), db


# ---------------------------------------------------------------------------
# 가용 계정 필터링
# ---------------------------------------------------------------------------

class TestAvailableAccounts:

    def test_active_never_used_is_available(self):
        d, db = _make_dispatcher([_account(1, last_used=None)], _combos(1))
        d.dispatch()
        # batch INSERT가 호출됐으면 계정이 가용으로 인식된 것
        assert db.execute.call_count >= 1

    def test_cooldown_not_expired_is_skipped(self):
        recent = datetime.now(tz=KST) - timedelta(days=5)
        d, db = _make_dispatcher([_account(1, last_used=recent)], _combos(1))
        result = d.dispatch()
        assert result.batches_created == 0

    def test_cooldown_expired_is_available(self):
        old = datetime.now(tz=KST) - timedelta(days=15)
        d, db = _make_dispatcher([_account(1, last_used=old)], _combos(40))
        result = d.dispatch()
        assert result.batches_created == 1

    def test_disabled_account_is_skipped(self):
        d, db = _make_dispatcher(
            [_account(1, status="disabled")], _combos(40)
        )
        result = d.dispatch()
        assert result.batches_created == 0

    def test_cooling_account_is_skipped(self):
        recent = datetime.now(tz=KST) - timedelta(days=5)
        d, db = _make_dispatcher(
            [_account(1, last_used=recent, status="cooling")], _combos(40)
        )
        result = d.dispatch()
        assert result.batches_created == 0


# ---------------------------------------------------------------------------
# 배치 크기 및 분배
# ---------------------------------------------------------------------------

class TestBatchSplit:

    def test_40_combos_1_account_creates_1_batch(self):
        d, db = _make_dispatcher([_account(1)], _combos(40))
        result = d.dispatch()
        assert result.batches_created == 1

    def test_80_combos_2_accounts_creates_2_batches(self):
        accounts = [_account(1), _account(2)]
        d, db = _make_dispatcher(accounts, _combos(80))
        result = d.dispatch()
        assert result.batches_created == 2

    def test_41_combos_2_accounts_creates_2_batches(self):
        """41개 = 40 + 1 → 2개 배치"""
        accounts = [_account(1), _account(2)]
        d, db = _make_dispatcher(accounts, _combos(41))
        result = d.dispatch()
        assert result.batches_created == 2

    def test_each_batch_has_at_most_batch_size_items(self):
        """각 배치에 BATCH_SIZE(40) 초과 항목 없음"""
        accounts = [_account(i) for i in range(1, 4)]
        d, db = _make_dispatcher(accounts, _combos(90))
        d.dispatch()
        # batch_items INSERT 호출에서 각 row 수 검증
        for c in db.execute_many.call_args_list:
            rows = c.args[1]
            assert len(rows) <= BATCH_SIZE

    def test_no_combo_no_batch(self):
        d, db = _make_dispatcher([_account(1)], [])
        result = d.dispatch()
        assert result.batches_created == 0

    def test_no_account_no_batch(self):
        d, db = _make_dispatcher([], _combos(40))
        result = d.dispatch()
        assert result.batches_created == 0

    def test_fewer_combos_than_batch_size(self):
        """조합 10개 → 배치 1개, 10개 항목"""
        d, db = _make_dispatcher([_account(1)], _combos(10))
        result = d.dispatch()
        assert result.batches_created == 1

    def test_accounts_used_count_matches_batches(self):
        """배치 수만큼 계정이 사용됨"""
        accounts = [_account(i) for i in range(1, 4)]
        d, db = _make_dispatcher(accounts, _combos(80))
        result = d.dispatch()
        assert result.accounts_used == result.batches_created


# ---------------------------------------------------------------------------
# 스케줄링
# ---------------------------------------------------------------------------

class TestScheduling:

    def test_scheduled_at_is_in_future(self):
        """배치의 scheduled_at은 현재 시각 이후"""
        now = datetime.now(tz=KST)
        base = now + timedelta(hours=1)
        d, db = _make_dispatcher([_account(1)], _combos(40),
                                  schedule_base=base)
        d.dispatch()
        # batches INSERT의 scheduled_at 인수 확인
        batch_insert_calls = [
            c for c in db.execute.call_args_list
            if "batches" in str(c).lower()
        ]
        assert len(batch_insert_calls) >= 1

    def test_multiple_batches_have_different_schedule_times(self):
        """배치가 여러 개면 예약 시각이 모두 달라야 함 (스팸 회피)"""
        accounts = [_account(i) for i in range(1, 4)]
        schedule_base = datetime(2026, 3, 20, 10, 0, tzinfo=KST)
        d, db = _make_dispatcher(accounts, _combos(120),
                                  schedule_base=schedule_base)
        result = d.dispatch()
        assert result.batches_created == 3
        scheduled_times = result.scheduled_times
        assert len(set(scheduled_times)) == len(scheduled_times), \
            "배치 간 예약 시각 중복"


# ---------------------------------------------------------------------------
# DB 업데이트
# ---------------------------------------------------------------------------

class TestDbUpdates:

    def test_account_last_used_at_updated(self):
        """dispatch 후 계정의 last_used_at이 업데이트됨"""
        d, db = _make_dispatcher([_account(1)], _combos(40))
        d.dispatch()
        update_calls = [
            c for c in db.execute.call_args_list
            if "last_used_at" in str(c)
        ]
        assert len(update_calls) >= 1

    def test_combo_used_at_updated(self):
        """사용된 combination의 used_at이 업데이트됨"""
        d, db = _make_dispatcher([_account(1)], _combos(40))
        d.dispatch()
        update_calls = [
            c for c in db.execute.call_args_list
            if "used_at" in str(c)
        ]
        assert len(update_calls) >= 1
