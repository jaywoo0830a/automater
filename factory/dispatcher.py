"""
factory/dispatcher.py
----------------------
Assigns pending combinations to available accounts in batches of 40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, case
from sqlalchemy.orm import Session

from factory.models import Account, Batch, BatchItem, Combination

KST             = timezone(timedelta(hours=9))
BATCH_SIZE      = 40
SCHEDULE_JITTER_MINUTES = 10


@dataclass
class DispatchResult:
    batches_created: int            = 0
    accounts_used:   int            = 0
    combos_assigned: int            = 0
    scheduled_times: list[datetime] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"DispatchResult("
            f"batches={self.batches_created}, "
            f"accounts_used={self.accounts_used}, "
            f"combos={self.combos_assigned})"
        )


class BatchDispatcher:
    def __init__(self, session: Session, schedule_base: datetime) -> None:
        self._session       = session
        self._schedule_base = schedule_base

    def dispatch(self) -> DispatchResult:
        now    = datetime.now(tz=KST)
        result = DispatchResult()

        accounts = self._available_accounts(now)
        combos   = self._pending_combinations()

        if not accounts or not combos:
            return result

        for idx, (account, chunk) in enumerate(zip(accounts, _chunk(combos, BATCH_SIZE))):
            scheduled_at = self._schedule_base + timedelta(minutes=idx * SCHEDULE_JITTER_MINUTES)
            self._create_batch(account, chunk, scheduled_at, now)
            result.batches_created += 1
            result.accounts_used   += 1
            result.combos_assigned += len(chunk)
            result.scheduled_times.append(scheduled_at)

        return result

    def _available_accounts(self, now: datetime) -> list[Account]:
        accounts = self._session.scalars(
            select(Account)
            .where(Account.status == "active")
            .order_by(case((Account.last_used_at.is_(None), 0), else_=1), Account.last_used_at.asc(), Account.id.asc())
        ).all()

        available = []
        for acc in accounts:
            last = acc.last_used_at
            if last is None:
                available.append(acc)
                continue
            if last.tzinfo is None:
                last = last.replace(tzinfo=KST)
            if now >= last + timedelta(days=acc.cooldown_days):
                available.append(acc)
        return available

    def _pending_combinations(self) -> list[Combination]:
        return self._session.scalars(
            select(Combination)
            .where(Combination.used_at.is_(None))
            .order_by(Combination.id.asc())
        ).all()

    def _create_batch(
        self,
        account:      Account,
        combos:       list[Combination],
        scheduled_at: datetime,
        now:          datetime,
    ) -> None:
        batch = Batch(
            campaign_id  = combos[0].campaign_id,
            account_id   = account.id,
            scheduled_at = scheduled_at,
            status       = "pending",
        )
        self._session.add(batch)
        self._session.flush()

        for combo in combos:
            self._session.add(BatchItem(
                batch_id       = batch.id,
                combination_id = combo.id,
                status         = "pending",
            ))

        account.last_used_at = now
        account.status       = "cooling"

        for combo in combos:
            combo.used_at = now


def _chunk(lst: list, size: int) -> list[list]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]
