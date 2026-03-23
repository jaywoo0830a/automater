"""
factory/dispatcher.py
----------------------
Assigns pending combinations to available accounts in batches of 40.

Supports:
    - campaign_id filtering for pending combinations
    - account_ids selection for manual account choice
    - Extracted pure filter functions for unit testing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence, TypeVar

from sqlalchemy import select, case
from sqlalchemy.orm import Session

from factory.models import Account, Batch, BatchItem, Combination

KST             = timezone(timedelta(hours=9))
BATCH_SIZE      = 40
SCHEDULE_JITTER_MINUTES = 10

_T = TypeVar("_T")


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


# ---------------------------------------------------------------------------
# Pure filter functions — testable without DB
# ---------------------------------------------------------------------------

def filter_accounts_by_ids(
    accounts: list[Any],
    account_ids: list[int] | None,
) -> list[Any]:
    """
    Filter accounts to only those whose id is in account_ids.

    Returns accounts in the same order as account_ids.
    When account_ids is None, returns all accounts unchanged.
    """
    if account_ids is None:
        return list(accounts)

    id_to_account = {a.id: a for a in accounts}
    return [id_to_account[aid] for aid in account_ids if aid in id_to_account]


def filter_accounts_by_availability(
    accounts: list[Any],
    now: datetime,
) -> list[Any]:
    """
    Filter accounts by status and cooldown period.

    Only accounts with status == "active" that are past their
    cooldown period (or never used) are returned.
    """
    available: list[Any] = []
    for acc in accounts:
        if acc.status != "active":
            continue
        last = acc.last_used_at
        if last is None:
            available.append(acc)
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=KST)
        if now >= last + timedelta(days=acc.cooldown_days):
            available.append(acc)
    return available


# ---------------------------------------------------------------------------
# BatchDispatcher
# ---------------------------------------------------------------------------

class BatchDispatcher:
    """
    Assigns pending combinations to accounts in batches.

    Args:
        session:       Active SQLAlchemy session.
        schedule_base: Base datetime for batch scheduling.
        campaign_id:   Filter pending combinations to this campaign.
                       None = all campaigns (original behavior).
    """

    def __init__(
        self,
        session: Session,
        schedule_base: datetime,
        campaign_id: int | None = None,
    ) -> None:
        self._session       = session
        self._schedule_base = schedule_base
        self._campaign_id   = campaign_id

    def dispatch(
        self,
        account_ids: list[int] | None = None,
    ) -> DispatchResult:
        """
        Assign pending combinations to available accounts.

        Args:
            account_ids: If provided, only use these accounts
                         (still checks availability/cooldown).
                         None = auto-select all available accounts.
        """
        now    = datetime.now(tz=KST)
        result = DispatchResult()

        accounts = self._load_accounts()
        accounts = filter_accounts_by_availability(accounts, now)
        accounts = filter_accounts_by_ids(accounts, account_ids)

        combos = self._pending_combinations()

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

    def _load_accounts(self) -> list[Account]:
        """Load all active accounts ordered by least recently used."""
        return list(self._session.scalars(
            select(Account)
            .where(Account.status == "active")
            .order_by(
                case((Account.last_used_at.is_(None), 0), else_=1),
                Account.last_used_at.asc(),
                Account.id.asc(),
            )
        ).all())

    def _pending_combinations(self) -> list[Combination]:
        """Load unused combinations, optionally filtered by campaign_id."""
        stmt = (
            select(Combination)
            .where(Combination.used_at.is_(None))
            .order_by(Combination.id.asc())
        )
        if self._campaign_id is not None:
            stmt = stmt.where(Combination.campaign_id == self._campaign_id)
        return list(self._session.scalars(stmt).all())

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


def _chunk(lst: list[_T], size: int) -> list[list[_T]]:
    """Split ``lst`` into sub-lists of at most ``size`` elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
