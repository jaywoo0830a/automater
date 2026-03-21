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
    CampaignKeywordPick,
    CampaignSlot,
    Combination,
    Keyword,
    SpacingRule,
    TemplateToken,
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
# CategoryPicks — clarifies the nested dict[int, list[int]]
# ---------------------------------------------------------------------------

# category_id → selected keyword IDs
CategoryPicks = dict[int, list[int]]


# ---------------------------------------------------------------------------
# ComboGenerator — orchestrates DB reads + build_combos + DB writes
# ---------------------------------------------------------------------------

class ComboGenerator:
    """
    Generate keyword combinations for a campaign and persist them.

    Picks are always loaded from CampaignKeywordPick table.
    Categories with no picks produce zero keywords (no implicit "use all").

    Args:
        session:     Active SQLAlchemy session (caller manages transaction).
        campaign_id: Target campaign ID.
    """

    def __init__(
        self,
        session:     Session,
        campaign_id: int,
    ) -> None:
        self._session     = session
        self._campaign_id = campaign_id

    def run(self) -> int:
        """Build combos and insert new ones. Returns the number of rows inserted."""
        slots = self._load_slots()
        if not slots:
            return 0

        picks = self._load_picks()
        kw_groups = self._build_keyword_groups(slots, picks)
        if kw_groups is None:
            return 0

        spacing_rule_ids = self._load_active_spacing_rule_ids()
        if not spacing_rule_ids:
            return 0

        combos = build_combos(kw_groups, spacing_rule_ids)
        return self._insert(combos, kw_groups)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_slots(self) -> Sequence[CampaignSlot]:
        return self._session.scalars(
            select(CampaignSlot)
            .join(TemplateToken)
            .where(TemplateToken.campaign_id == self._campaign_id)
            .order_by(TemplateToken.sort_order)
        ).all()

    def _load_picks(self) -> CategoryPicks:
        """Load keyword picks from DB, keyed by category_id."""
        picks_rows = self._session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == self._campaign_id,
            )
        ).all()
        result: CategoryPicks = {}
        for pick in picks_rows:
            result.setdefault(pick.category_id, []).append(pick.keyword_id)
        return result

    def _build_keyword_groups(
        self,
        slots: Sequence[CampaignSlot],
        picks: CategoryPicks,
    ) -> list[list[int]] | None:
        """
        Build one keyword-ID list per slot from picks.

        Categories with no picks produce zero keywords — no implicit "use all".
        Returns None if any slot resolves to zero keywords
        (makes the entire Cartesian product empty).
        """
        kw_groups: list[list[int]] = []
        for slot in slots:
            cat_id = slot.category_id
            picked = picks.get(cat_id)

            if not picked:
                return None

            stmt = (
                select(Keyword)
                .where(
                    Keyword.id.in_(picked),
                    Keyword.active == True,  # noqa: E712
                )
                .order_by(Keyword.sort_order, Keyword.id)
            )

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
    ) -> int:
        """
        Insert new combinations, skipping duplicates.

        Returns the number of actually inserted rows.
        """
        all_kw_ids = {kw_id for group in kw_groups for kw_id in group}
        kw_by_id: dict[int, Keyword] = {
            kw.id: kw
            for kw in self._session.scalars(
                select(Keyword).where(Keyword.id.in_(all_kw_ids))
            ).all()
        }

        existing = self._load_existing_fingerprints()
        inserted = 0

        for spec in combos:
            fingerprint = (frozenset(spec.keyword_ids), spec.spacing_rule_id)
            if fingerprint in existing:
                continue

            combination = Combination(
                campaign_id     = self._campaign_id,
                spacing_rule_id = spec.spacing_rule_id,
            )
            combination.keywords = [kw_by_id[kid] for kid in spec.keyword_ids]
            self._session.add(combination)
            existing.add(fingerprint)
            inserted += 1

        return inserted

    def _load_existing_fingerprints(self) -> set[tuple[frozenset[int], int]]:
        """Load fingerprints of all existing combinations for this campaign."""
        combos = self._session.scalars(
            select(Combination).where(
                Combination.campaign_id == self._campaign_id,
            )
        ).all()
        return {
            (frozenset(kw.id for kw in c.keywords), c.spacing_rule_id)
            for c in combos
        }
