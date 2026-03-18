"""
factory/keyword_picker.py
--------------------------
CampaignKeywordPicker — campaign_keyword_picks 를 관리한다.
"""

from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from factory.models import (
    CampaignKeywordPick,
    CampaignSlot,
    Keyword,
    KeywordCategory,
)


class CampaignKeywordPicker:
    def __init__(self, session: Session, campaign_id: int) -> None:
        self._session     = session
        self._campaign_id = campaign_id

    def _slots(self) -> list[CampaignSlot]:
        return self._session.scalars(
            select(CampaignSlot)
            .where(CampaignSlot.campaign_id == self._campaign_id)
            .order_by(CampaignSlot.sort_order)
        ).all()

    def _active_keywords_for_campaign(self) -> list[Keyword]:
        return self._session.scalars(
            select(Keyword)
            .join(CampaignSlot, Keyword.category_id == CampaignSlot.category_id)
            .where(
                CampaignSlot.campaign_id == self._campaign_id,
                Keyword.active == True,  # noqa: E712
            )
        ).all()

    # ------------------------------------------------------------------
    # picks 저장
    # ------------------------------------------------------------------

    def pick(self, category_slug: str, values: list[str]) -> int:
        slots = self._slots()
        slot  = next((s for s in slots if s.category.slug == category_slug), None)
        if slot is None:
            raise ValueError(
                f"category slug '{category_slug}' 없음. "
                f"사용 가능: {[s.category.slug for s in slots]}"
            )

        cat_id = slot.category_id

        if values:
            cat_kws = {
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
            selected_ids = [cat_kws[v] for v in values]
        else:
            selected_ids = []

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

    # ------------------------------------------------------------------
    # picks 조회
    # ------------------------------------------------------------------

    def list_picks(self) -> dict[str, list[str]]:
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

    def get_picked_keyword_ids(self) -> dict[int, list[int] | None]:
        slots = self._slots()
        picks = self._session.scalars(
            select(CampaignKeywordPick)
            .where(CampaignKeywordPick.campaign_id == self._campaign_id)
        ).all()

        result: dict[int, list[int] | None] = {s.category_id: None for s in slots}
        for pick in picks:
            cat_id = pick.category_id
            if cat_id in result:
                if result[cat_id] is None:
                    result[cat_id] = []
                result[cat_id].append(pick.keyword_id)
        return result
