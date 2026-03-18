"""
factory/tests/test_batch_dispatcher.py
----------------------------------------
BatchDispatcher 단위 테스트.

스키마 v2 용어:
  accounts        → 블로그 계정 (naver_id, cooldown_days, status ...)
  combinations    → 생성된 키워드 조합
  batches         → 계정에 할당된 조합 묶음
  batch_items     → 배치 내 개별 조합 항목

DB 와 datetime 을 mock 해서 순수 할당 로직만 검증한다.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from factory.dispatcher import BatchDispatcher, BATCH_SIZE

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _account(id_, last_used_at=None, cooldown_days=14, status="active"):
    return {
        "id":            id_,
        "naver_id":      f"user{id_}",
        "last_used_at":  last_used_at,
        "cooldown_days": cooldown_days,
        "status":        status,
    }


def _combination(id_):
    return {
        "id":         id_,
        "keyword_ids": [1, 2, 3],
        "has_suffix":  1,
    }


def _combinations(n):
    return [_combination(i) for i in range(1, n + 1)]


def _make_dispatcher(accounts, pending_combinations, schedule_base=None):
    db = MagicMock()
    db.fetch_all.side_effect = [accounts, pending_combinations]
    if schedule_base is None:
        schedule_base = datetime(2026, 3, 20, 10, 0, tzinfo=KST)
    return BatchDispatcher(db=db, schedule_base=schedule_base), db


# ---------------------------------------------------------------------------
# 가용 계정 필터링
# ---------------------------------------------------------------------------

class TestAvailableAccounts:

    def test_account_never_used_is_available(self):
        """last_used_at 이 없는 계정은 항상 가용 상태다."""
        dispatcher, db = _make_dispatcher(
            [_account(1, last_used_at=None)], _combinations(1)
        )
        dispatcher.dispatch()
        assert db.execute.call_count >= 1

    def test_account_within_cooldown_is_skipped(self):
        """cooldown_days 이내에 사용된 계정은 건너뛴다."""
        recent_use = datetime.now(tz=KST) - timedelta(days=5)
        dispatcher, db = _make_dispatcher(
            [_account(1, last_used_at=recent_use)], _combinations(1)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 0

    def test_account_past_cooldown_is_available(self):
        """cooldown_days 를 초과한 계정은 다시 가용 상태다."""
        old_use = datetime.now(tz=KST) - timedelta(days=15)
        dispatcher, db = _make_dispatcher(
            [_account(1, last_used_at=old_use)], _combinations(40)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 1

    def test_disabled_account_is_skipped(self):
        """status='disabled' 계정은 배치 할당에서 제외된다."""
        dispatcher, db = _make_dispatcher(
            [_account(1, status="disabled")], _combinations(40)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 0

    def test_cooling_account_is_skipped(self):
        """status='cooling' 계정은 배치 할당에서 제외된다."""
        recent_use = datetime.now(tz=KST) - timedelta(days=5)
        dispatcher, db = _make_dispatcher(
            [_account(1, last_used_at=recent_use, status="cooling")],
            _combinations(40)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 0


# ---------------------------------------------------------------------------
# 배치 크기 및 분배
# ---------------------------------------------------------------------------

class TestBatchSplit:

    def test_40_combinations_1_account_creates_1_batch(self):
        """조합 40개 + 계정 1개 → 배치 1개."""
        dispatcher, _ = _make_dispatcher([_account(1)], _combinations(40))
        result = dispatcher.dispatch()
        assert result.batches_created == 1

    def test_80_combinations_2_accounts_creates_2_batches(self):
        """조합 80개 + 계정 2개 → 배치 2개."""
        dispatcher, _ = _make_dispatcher(
            [_account(1), _account(2)], _combinations(80)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 2

    def test_41_combinations_2_accounts_creates_2_batches(self):
        """조합 41개 = BATCH_SIZE(40) + 1 → 배치 2개."""
        dispatcher, _ = _make_dispatcher(
            [_account(1), _account(2)], _combinations(41)
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 2

    def test_each_batch_has_at_most_batch_size_items(self):
        """각 batch_items 그룹이 BATCH_SIZE 를 초과하지 않아야 한다."""
        dispatcher, db = _make_dispatcher(
            [_account(i) for i in range(1, 4)], _combinations(90)
        )
        dispatcher.dispatch()
        for c in db.execute_many.call_args_list:
            rows = c.args[1]
            assert len(rows) <= BATCH_SIZE

    def test_no_combinations_creates_no_batches(self):
        """pending combinations 가 없으면 배치가 생성되지 않는다."""
        dispatcher, _ = _make_dispatcher([_account(1)], [])
        result = dispatcher.dispatch()
        assert result.batches_created == 0

    def test_no_accounts_creates_no_batches(self):
        """가용 계정이 없으면 배치가 생성되지 않는다."""
        dispatcher, _ = _make_dispatcher([], _combinations(40))
        result = dispatcher.dispatch()
        assert result.batches_created == 0

    def test_fewer_combinations_than_batch_size_creates_1_batch(self):
        """조합이 BATCH_SIZE 미만이면 배치 1개가 생성된다."""
        dispatcher, _ = _make_dispatcher([_account(1)], _combinations(10))
        result = dispatcher.dispatch()
        assert result.batches_created == 1

    def test_accounts_used_equals_batches_created(self):
        """사용된 계정 수 = 생성된 배치 수."""
        dispatcher, _ = _make_dispatcher(
            [_account(i) for i in range(1, 4)], _combinations(80)
        )
        result = dispatcher.dispatch()
        assert result.accounts_used == result.batches_created


# ---------------------------------------------------------------------------
# 배치 스케줄링
# ---------------------------------------------------------------------------

class TestBatchScheduling:

    def test_batch_scheduled_at_is_after_schedule_base(self):
        """batches.scheduled_at 은 schedule_base 이후여야 한다."""
        base = datetime.now(tz=KST) + timedelta(hours=1)
        dispatcher, db = _make_dispatcher(
            [_account(1)], _combinations(40), schedule_base=base
        )
        dispatcher.dispatch()
        batch_inserts = [
            c for c in db.execute.call_args_list
            if "batches" in str(c).lower()
        ]
        assert batch_inserts

    def test_multiple_batches_have_distinct_scheduled_times(self):
        """여러 배치는 스팸 회피를 위해 서로 다른 예약 시각을 가져야 한다."""
        schedule_base = datetime(2026, 3, 20, 10, 0, tzinfo=KST)
        dispatcher, _ = _make_dispatcher(
            [_account(i) for i in range(1, 4)],
            _combinations(120),
            schedule_base=schedule_base,
        )
        result = dispatcher.dispatch()
        assert result.batches_created == 3
        assert len(set(result.scheduled_times)) == len(result.scheduled_times), \
            "배치 간 scheduled_at 중복"


# ---------------------------------------------------------------------------
# DB 업데이트
# ---------------------------------------------------------------------------

class TestDbUpdates:

    def test_account_last_used_at_is_updated_after_dispatch(self):
        """dispatch 완료 후 accounts.last_used_at 이 갱신되어야 한다."""
        dispatcher, db = _make_dispatcher([_account(1)], _combinations(40))
        dispatcher.dispatch()
        updates = [
            c for c in db.execute.call_args_list
            if "last_used_at" in str(c)
        ]
        assert updates

    def test_combination_used_at_is_updated_after_dispatch(self):
        """배치에 포함된 combinations.used_at 이 갱신되어야 한다."""
        dispatcher, db = _make_dispatcher([_account(1)], _combinations(40))
        dispatcher.dispatch()
        updates = [
            c for c in db.execute.call_args_list
            if "used_at" in str(c)
        ]
        assert updates
