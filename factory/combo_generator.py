"""
factory/combo_generator.py
----------------------------
Generates the Cartesian product of campaign keywords and inserts
them into the combinations + combination_keywords tables.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.models import (
    CampaignSlot,
    Combination,
    Keyword,
    SpacingRule,
)


# ---------------------------------------------------------------------------
# ComboSpec — typed replacement for the raw dict that build_combos returned
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ComboSpec:
    """One row of the Cartesian product, ready to be inserted into DB."""
    keyword_ids:     list[int]
    spacing_rule_id: int


# ---------------------------------------------------------------------------
# Pure function — testable without DB
# ---------------------------------------------------------------------------

def build_combos(
    kw_groups:          list[list[int]],
    spacing_rule_ids:   list[int],
) -> list[ComboSpec]:
    """
    Pure Cartesian product — no DB dependency.

    Returns a list of ComboSpec, one per unique
    (keyword_ids, spacing_rule_id) tuple.
    """
    combos: list[ComboSpec] = []
    for spacing_id in spacing_rule_ids:
        for combo_kws in itertools.product(*kw_groups):
            combos.append(ComboSpec(
                keyword_ids=list(combo_kws),
                spacing_rule_id=spacing_id,
            ))
    return combos


# ---------------------------------------------------------------------------
# CategoryPicks — clarifies the nested dict[int, list[int] | None]
# ---------------------------------------------------------------------------

# category_id → selected keyword IDs, or None meaning "use all active"
CategoryPicks = dict[int, list[int] | None]


# ---------------------------------------------------------------------------
# ComboGenerator — orchestrates DB reads + build_combos + DB writes
# ---------------------------------------------------------------------------

class ComboGenerator:
    """
    Generate keyword combinations for a campaign and persist them.

    Args:
        session:     Active SQLAlchemy session (caller manages transaction).
        campaign_id: Target campaign ID.
        picks:       Per-category keyword filter. None values mean "all active".
    """

    def __init__(
        self,
        session:     Session,
        campaign_id: int,
        picks:       CategoryPicks | None = None,
    ) -> None:
        self._session     = session
        self._campaign_id = campaign_id
        self._picks       = picks or {}

    def run(self) -> int:
        """Build combos and insert them. Returns the number of rows inserted."""
        slots = self._load_slots()
        if not slots:
            return 0

        kw_groups = self._build_keyword_groups(slots)
        if kw_groups is None:
            return 0

        spacing_rule_ids = self._load_active_spacing_rule_ids()
        if not spacing_rule_ids:
            return 0

        combos = build_combos(kw_groups, spacing_rule_ids)
        self._insert(combos, kw_groups)
        return len(combos)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_slots(self) -> Sequence[CampaignSlot]:
        return self._session.scalars(
            select(CampaignSlot)
            .where(CampaignSlot.campaign_id == self._campaign_id)
            .order_by(CampaignSlot.sort_order)
        ).all()

    def _build_keyword_groups(
        self, slots: Sequence[CampaignSlot],
    ) -> list[list[int]] | None:
        """
        Build one keyword-ID list per slot.

        Returns None if any slot resolves to zero keywords
        (makes the entire Cartesian product empty).
        """
        kw_groups: list[list[int]] = []
        for slot in slots:
            cat_id = slot.category_id
            picked = self._picks.get(cat_id)

            if picked is not None and len(picked) == 0:
                return None

            stmt = (
                select(Keyword)
                .where(Keyword.category_id == cat_id, Keyword.active == True)  # noqa: E712
                .order_by(Keyword.sort_order, Keyword.id)
            )
            if picked is not None:
                stmt = stmt.where(Keyword.id.in_(picked))

            kws = self._session.scalars(stmt).all()
            if not kws:
                return None
            kw_groups.append([kw.id for kw in kws])
        return kw_groups

    def _load_active_spacing_rule_ids(self) -> list[int]:
        rules = self._session.scalars(
            select(SpacingRule)
            .where(
                SpacingRule.campaign_id == self._campaign_id,
                SpacingRule.active == True,  # noqa: E712
            )
        ).all()
        return [r.id for r in rules]

    def _insert(
        self,
        combos:    list[ComboSpec],
        kw_groups: list[list[int]],
    ) -> None:
        all_kw_ids = {kw_id for group in kw_groups for kw_id in group}
        kw_by_id: dict[int, Keyword] = {
            kw.id: kw
            for kw in self._session.scalars(
                select(Keyword).where(Keyword.id.in_(all_kw_ids))
            ).all()
        }

        for spec in combos:
            combination = Combination(
                campaign_id     = self._campaign_id,
                spacing_rule_id = spec.spacing_rule_id,
            )
            combination.keywords = [kw_by_id[kid] for kid in spec.keyword_ids]
            self._session.add(combination)
