"""
factory/tests/test_batch_dispatcher.py
----------------------------------------
BatchDispatcher 단위 테스트.
SQLAlchemy 2.0 select() 스타일로 DB 상태를 검증한다.
"""

import random
import string
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.dispatcher import BatchDispatcher, BATCH_SIZE
from factory.models import Account, Batch, BatchItem, Combination, Platform
from factory.tests.conftest import make_campaign

KST           = timezone(timedelta(hours=9))
SCHEDULE_BASE = datetime(2026, 3, 20, 10, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_account(session: Session, *, last_used_at=None, cooldown_days=14, status="active") -> Account:
    platform = session.scalars(select(Platform)).first()
    suffix   = "".join(random.choices(string.ascii_lowercase, k=6))
    acc = Account(
        platform_id   = platform.id,
        username      = f"user_{suffix}",
        password_enc  = "enc",
        cooldown_days = cooldown_days,
        last_used_at  = last_used_at,
        status        = status,
    )
    session.add(acc)
    session.flush()
    return acc


def _add_combinations(session: Session, campaign, n: int) -> list[Combination]:
    combos = [
        Combination(campaign_id=campaign.id, used_at=None, config={"has_suffix": 0})
        for _ in range(n)
    ]
    session.add_all(combos)
    session.flush()
    return combos


def _dispatch(session: Session, base=SCHEDULE_BASE) -> "DispatchResult":
    return BatchDispatcher(session=session, schedule_base=base).dispatch()


# ---------------------------------------------------------------------------
# 가용 계정 필터링
# ---------------------------------------------------------------------------

class TestAvailableAccounts:

    def test_never_used_account_is_available(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session, last_used_at=None)
        _add_combinations(session, campaign, 1)
        assert _dispatch(session).batches_created == 1

    def test_within_cooldown_is_skipped(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session, last_used_at=datetime.now(tz=KST) - timedelta(days=5))
        _add_combinations(session, campaign, 1)
        assert _dispatch(session).batches_created == 0

    def test_past_cooldown_is_available(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session, last_used_at=datetime.now(tz=KST) - timedelta(days=15))
        _add_combinations(session, campaign, BATCH_SIZE)
        assert _dispatch(session).batches_created == 1

    def test_non_active_status_is_skipped(self, session: Session):
        campaign = make_campaign(session)
        for status in ("disabled", "cooling"):
            _add_account(session, status=status)
        _add_combinations(session, campaign, 1)
        assert _dispatch(session).batches_created == 0


# ---------------------------------------------------------------------------
# 배치 분배
# ---------------------------------------------------------------------------

class TestBatchSplit:

    def test_40_combos_1_account_makes_1_batch(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session)
        _add_combinations(session, campaign, 40)
        assert _dispatch(session).batches_created == 1

    def test_41_combos_2_accounts_makes_2_batches(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session)
        _add_account(session)
        _add_combinations(session, campaign, 41)
        assert _dispatch(session).batches_created == 2

    def test_batch_items_never_exceed_batch_size(self, session: Session):
        campaign = make_campaign(session)
        for _ in range(3):
            _add_account(session)
        _add_combinations(session, campaign, 90)
        _dispatch(session)
        session.flush()

        for batch in session.scalars(select(Batch)).all():
            assert len(batch.items) <= BATCH_SIZE

    def test_no_combos_makes_no_batches(self, session: Session):
        make_campaign(session)
        _add_account(session)
        assert _dispatch(session).batches_created == 0

    def test_no_accounts_makes_no_batches(self, session: Session):
        campaign = make_campaign(session)
        _add_combinations(session, campaign, 10)
        assert _dispatch(session).batches_created == 0


# ---------------------------------------------------------------------------
# 스케줄링
# ---------------------------------------------------------------------------

class TestScheduling:

    def test_multiple_batches_have_distinct_scheduled_times(self, session: Session):
        campaign = make_campaign(session)
        for _ in range(3):
            _add_account(session)
        _add_combinations(session, campaign, 120)
        result = _dispatch(session)
        assert len(set(result.scheduled_times)) == len(result.scheduled_times)


# ---------------------------------------------------------------------------
# DB 상태 검증
# ---------------------------------------------------------------------------

class TestDbState:

    def test_account_set_to_cooling(self, session: Session):
        campaign = make_campaign(session)
        acc      = _add_account(session)
        _add_combinations(session, campaign, 1)
        _dispatch(session)
        assert acc.status == "cooling"

    def test_combination_used_at_set(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session)
        combos = _add_combinations(session, campaign, 5)
        _dispatch(session)
        assert all(c.used_at is not None for c in combos)

    def test_used_combinations_not_redispatched(self, session: Session):
        campaign = make_campaign(session)
        _add_account(session)
        _add_combinations(session, campaign, 5)
        _dispatch(session)
        session.flush()

        _add_account(session)
        assert _dispatch(session).batches_created == 0
