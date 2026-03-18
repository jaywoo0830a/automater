"""
factory/combo_generator.py
----------------------------
캠페인의 카테시안 곱을 생성해 combinations + combination_keywords 에 삽입.
"""

from __future__ import annotations

import itertools

from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.models import (
    Campaign,
    CampaignSlot,
    Combination,
    Keyword,
    SpacingRule,
)


def build_combos(
    kw_groups: list[list[int]],
    spacing_rule_ids: list[int],
    has_suffix_options: list[int],
) -> list[dict]:
    """
    순수 카테시안 곱 — DB 없이 테스트 가능.

    Returns:
        [{"keyword_ids": [...], "spacing_rule_id": int, "has_suffix": int}, ...]
    """
    combos: list[dict] = []
    for spacing_id, has_suffix in itertools.product(spacing_rule_ids, has_suffix_options):
        for combo_kws in itertools.product(*kw_groups):
            combos.append({
                "keyword_ids":     list(combo_kws),
                "spacing_rule_id": spacing_id,
                "has_suffix":      has_suffix,
            })
    return combos


class ComboGenerator:
    def __init__(
        self,
        session: Session,
        campaign_id: int,
        picks: dict[int, list[int] | None] | None = None,
    ) -> None:
        self._session     = session
        self._campaign_id = campaign_id
        self._picks       = picks or {}

    def run(self) -> int:
        # 1. Campaign config
        campaign = self._session.get(Campaign, self._campaign_id)
        config   = (campaign.config or {}) if campaign else {}
        has_suffix_options: list[int] = config.get("has_suffix_options", [0, 1])

        # 2. Slots
        slots = self._session.scalars(
            select(CampaignSlot)
            .where(CampaignSlot.campaign_id == self._campaign_id)
            .order_by(CampaignSlot.sort_order)
        ).all()
        if not slots:
            return 0

        # 3. Keyword groups
        kw_groups: list[list[int]] = []
        for slot in slots:
            cat_id = slot.category_id
            picked = self._picks.get(cat_id)

            if picked is not None and len(picked) == 0:
                return 0

            stmt = (
                select(Keyword)
                .where(Keyword.category_id == cat_id, Keyword.active == True)  # noqa: E712
                .order_by(Keyword.sort_order, Keyword.id)
            )
            if picked is not None:
                stmt = stmt.where(Keyword.id.in_(picked))

            kws = self._session.scalars(stmt).all()
            if not kws:
                return 0
            kw_groups.append([kw.id for kw in kws])

        # 4. Spacing rules
        spacing_rules = self._session.scalars(
            select(SpacingRule)
            .where(
                SpacingRule.campaign_id == self._campaign_id,
                SpacingRule.active == True,  # noqa: E712
            )
        ).all()
        if not spacing_rules:
            return 0

        # 5. Build & insert
        combos       = build_combos(kw_groups, [sr.id for sr in spacing_rules], has_suffix_options)
        all_kw_ids   = {kw_id for group in kw_groups for kw_id in group}
        kw_by_id     = {
            kw.id: kw
            for kw in self._session.scalars(
                select(Keyword).where(Keyword.id.in_(all_kw_ids))
            ).all()
        }

        for c in combos:
            combination          = Combination(
                campaign_id     = self._campaign_id,
                spacing_rule_id = c["spacing_rule_id"],
                config          = {"has_suffix": c["has_suffix"]},
            )
            combination.keywords = [kw_by_id[kid] for kid in c["keyword_ids"]]
            self._session.add(combination)

        return len(combos)
