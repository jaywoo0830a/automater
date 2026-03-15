"""
factory/dispatcher.py
----------------------
Assigns pending combinations to available accounts in batches of 40.

Rules
-----
- An account is available when:
    status = 'active'  AND
    (last_used_at IS NULL  OR  last_used_at + cooldown_days < NOW())
- Combinations are assigned FIFO (id ASC, unused first).
- Each batch gets a scheduled_at that is staggered by SCHEDULE_JITTER_MINUTES
  from schedule_base so posts don't all go live at the same second.
- All DB writes are done in a single transaction per dispatch() call.

Usage:
    from factory.db import Database
    from factory.dispatcher import BatchDispatcher
    from datetime import datetime, timedelta, timezone

    KST  = timezone(timedelta(hours=9))
    base = datetime.now(tz=KST).replace(minute=0, second=0, microsecond=0) \
           + timedelta(hours=2)

    with Database.from_env() as db:
        dispatcher = BatchDispatcher(db=db, schedule_base=base)
        result     = dispatcher.dispatch()
        print(result)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BATCH_SIZE = 40                  # 계정당 최대 포스팅 수
SCHEDULE_JITTER_MINUTES = 10     # 배치 간 예약 시각 간격 (분)

_FETCH_ACCOUNTS_SQL = """
    SELECT id, naver_id, last_used_at, cooldown_days, status
    FROM   accounts
    WHERE  status = 'active'
    ORDER  BY last_used_at ASC NULLS FIRST, id ASC
"""

_FETCH_PENDING_COMBOS_SQL = """
    SELECT id, region_id, subject, learning_type, has_space, has_suffix
    FROM   combinations
    WHERE  used_at IS NULL
    ORDER  BY id ASC
"""

_INSERT_BATCH_SQL = """
    INSERT INTO batches (account_id, scheduled_at, status)
    VALUES (%s, %s, 'pending')
"""

_INSERT_BATCH_ITEMS_SQL = """
    INSERT IGNORE INTO batch_items (batch_id, combination_id, status)
    VALUES (%s, %s, 'pending')
"""

_UPDATE_ACCOUNT_SQL = """
    UPDATE accounts
    SET    last_used_at = %s,
           status       = 'cooling'
    WHERE  id = %s
"""

_UPDATE_COMBO_USED_AT_SQL = """
    UPDATE combinations
    SET    used_at = %s
    WHERE  id IN ({placeholders})
"""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    batches_created:  int           = 0
    accounts_used:    int           = 0
    combos_assigned:  int           = 0
    scheduled_times:  list[datetime] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"DispatchResult("
            f"batches={self.batches_created}, "
            f"accounts_used={self.accounts_used}, "
            f"combos={self.combos_assigned})"
        )


# ---------------------------------------------------------------------------
# BatchDispatcher
# ---------------------------------------------------------------------------

class BatchDispatcher:
    """
    Assigns pending combinations to available accounts.

    Args:
        db:            Database instance.
        schedule_base: KST-aware datetime — first batch starts here.
                       Subsequent batches are staggered by SCHEDULE_JITTER_MINUTES.
    """

    def __init__(self, db, schedule_base: datetime) -> None:
        self._db            = db
        self._schedule_base = schedule_base

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dispatch(self) -> DispatchResult:
        """
        Main entry point.

        1. Fetch available accounts and pending combinations.
        2. Split combinations into BATCH_SIZE chunks.
        3. Assign each chunk to one account.
        4. Insert batches + batch_items, update accounts + combinations.

        Returns:
            DispatchResult with summary counts.
        """
        now      = datetime.now(tz=KST)
        result   = DispatchResult()

        accounts = self._available_accounts(now)
        combos   = self._db.fetch_all(_FETCH_PENDING_COMBOS_SQL)

        if not accounts or not combos:
            return result

        chunks   = _chunk(combos, BATCH_SIZE)
        pairs    = list(zip(accounts, chunks))   # 계정 수 또는 청크 수 중 작은 쪽

        for idx, (account, chunk) in enumerate(pairs):
            scheduled_at = self._schedule_base + timedelta(
                minutes=idx * SCHEDULE_JITTER_MINUTES
            )
            self._create_batch(account, chunk, scheduled_at, now)

            result.batches_created += 1
            result.accounts_used   += 1
            result.combos_assigned += len(chunk)
            result.scheduled_times.append(scheduled_at)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _available_accounts(self, now: datetime) -> list[dict]:
        """Return accounts whose cooldown has expired."""
        all_active = self._db.fetch_all(_FETCH_ACCOUNTS_SQL)
        available  = []
        for acc in all_active:
            if acc["status"] != "active":
                continue
            last = acc["last_used_at"]
            if last is None:
                available.append(acc)
                continue
            # last_used_at may come as naive datetime from MySQL driver
            if last.tzinfo is None:
                last = last.replace(tzinfo=KST)
            cooldown_end = last + timedelta(days=acc["cooldown_days"])
            if now >= cooldown_end:
                available.append(acc)
        return available

    def _create_batch(
        self,
        account: dict,
        combos:  list[dict],
        scheduled_at: datetime,
        now: datetime,
    ) -> None:
        """Insert one batch + its items, update account + combo used_at."""
        # 1. Insert batch row
        self._db.execute(
            _INSERT_BATCH_SQL,
            (account["id"], scheduled_at),
        )
        batch_id = self._db.last_insert_id()

        # 2. Insert batch_items
        item_rows = [(batch_id, c["id"]) for c in combos]
        self._db.execute_many(_INSERT_BATCH_ITEMS_SQL, item_rows)

        # 3. Mark account as cooling
        self._db.execute(_UPDATE_ACCOUNT_SQL, (now, account["id"]))

        # 4. Mark combinations as used
        combo_ids    = [c["id"] for c in combos]
        placeholders = ", ".join(["%s"] * len(combo_ids))
        self._db.execute(
            _UPDATE_COMBO_USED_AT_SQL.format(placeholders=placeholders),
            tuple(combo_ids),
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _chunk(lst: list, size: int) -> list[list]:
    """Split lst into sublists of at most size elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
