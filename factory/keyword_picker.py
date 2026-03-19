"""
factory/keyword_picker.py
--------------------------
CampaignKeywordPicker — manages campaign_keyword_picks.

Public API (save ↔ load symmetry):
    save_picks(category_slug, values)  → int            (write)
    load_picks()                       → dict[str, …]   (read by slug)
    load_pick_ids()                    → dict[int, …]    (read by category_id)
"""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from factory.models import (
    CampaignKeywordPick,
    CampaignSlot,
    Keyword,
    KeywordCategory,
)

# Re-export the type alias so callers can type-hint without importing models
from factory.combo_generator import CategoryPicks


class CampaignKeywordPicker:
    """
    Read/write keyword selections for a single campaign.

    Args:
        session:     Active SQLAlchemy session (caller manages transaction).
        campaign_id: Target campaign ID.
    """

    def __init__(self, session: Session, campaign_id: int) -> None:
        self._session     = session
        self._campaign_id = campaign_id

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _slots(self) -> Sequence[CampaignSlot]:
        return self._session.scalars(
            select(CampaignSlot)
            .where(CampaignSlot.campaign_id == self._campaign_id)
            .order_by(CampaignSlot.sort_order)
        ).all()

    def _active_keywords_for_campaign(self) -> Sequence[Keyword]:
        return self._session.scalars(
            select(Keyword)
            .join(CampaignSlot, Keyword.category_id == CampaignSlot.category_id)
            .where(
                CampaignSlot.campaign_id == self._campaign_id,
                Keyword.active == True,  # noqa: E712
            )
        ).all()

    def _resolve_slot(self, category_slug: str) -> CampaignSlot:
        """
        Find the CampaignSlot matching ``category_slug``.

        Raises:
            ValueError: If no slot matches the slug.
        """
        slots = self._slots()
        slot = next((s for s in slots if s.category.slug == category_slug), None)
        if slot is None:
            available = [s.category.slug for s in slots]
            raise ValueError(
                f"category slug '{category_slug}' 없음. "
                f"사용 가능: {available}"
            )
        return slot

    # ------------------------------------------------------------------
    # Write — save_picks
    # ------------------------------------------------------------------

    def save_picks(self, category_slug: str, values: list[str]) -> int:
        """
        Replace all picks for ``category_slug`` with ``values``.

        Pass an empty list to clear the picks for that category
        (meaning "use all active keywords").

        Args:
            category_slug: e.g. "region", "subject"
            values:        Keyword values to select, e.g. ["강남구", "수원시"]

        Returns:
            Number of keywords saved.

        Raises:
            ValueError: Unknown category_slug or unknown keyword values.
        """
        slot   = self._resolve_slot(category_slug)
        cat_id = slot.category_id

        selected_ids = self._resolve_keyword_ids(cat_id, category_slug, values)

        self._session.execute(
            delete(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == self._campaign_id,
                CampaignKeywordPick.category_id == cat_id,
            )
        )

        for kw_id in selected_ids:
            self._session.add(
                CampaignKeywordPick(
                    campaign_id=self._campaign_id,
                    category_id=cat_id,
                    keyword_id=kw_id,
                )
            )

        return len(selected_ids)

    def _resolve_keyword_ids(
        self, cat_id: int, category_slug: str, values: list[str],
    ) -> list[int]:
        """Map human-readable keyword values to their IDs, validating each."""
        if not values:
            return []

        cat_kws: dict[str, int] = {
            kw.value: kw.id
            for kw in self._active_keywords_for_campaign()
            if kw.category_id == cat_id
        }
        unknown = [v for v in values if v not in cat_kws]
        if unknown:
            raise ValueError(
                f"없는 키워드: {unknown}. "
                f"'{category_slug}' 사용 가능: {list(cat_kws.keys())}"
            )
        return [cat_kws[v] for v in values]

    # ------------------------------------------------------------------
    # Read — load_picks / load_pick_ids  (symmetric pair)
    # ------------------------------------------------------------------

    def load_picks(self) -> dict[str, list[str]]:
        """
        Return current picks keyed by category slug (human-readable).

        Returns:
            {"region": ["강남구", "수원시"], "subject": [], ...}
            Empty list means "no filter — use all active keywords".
        """
        slots = self._slots()
        picks = self._session.scalars(
            select(CampaignKeywordPick)
            .where(CampaignKeywordPick.campaign_id == self._campaign_id)
        ).all()

        result: dict[str, list[str]] = {s.category.slug: [] for s in slots}
        for pick in picks:
            slug = pick.category.slug
            if slug in result:
                result[slug].append(pick.keyword.value)
        return result

    def load_pick_ids(self) -> CategoryPicks:
        """
        Return current picks keyed by category_id (machine-readable).

        Returns:
            {1: [101, 102], 2: None, 3: None}
            None means "no filter — use all active keywords".
        """
        slots = self._slots()
        picks = self._session.scalars(
            select(CampaignKeywordPick)
            .where(CampaignKeywordPick.campaign_id == self._campaign_id)
        ).all()

        result: CategoryPicks = {s.category_id: None for s in slots}
        for pick in picks:
            cat_id = pick.category_id
            if cat_id in result:
                if result[cat_id] is None:
                    result[cat_id] = []
                result[cat_id].append(pick.keyword_id)
        return result
