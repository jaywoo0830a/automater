"""
api/routes/combinations.py — listCombinations, previewSeed, seedCombinations, clearCombinations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from api.deps import Db, CurrentUser
from api.schemas import CombinationOut, SeedResult, ClearResult, SeedPreview
from factory.models import (
    Campaign, CampaignSlot, CampaignKeywordPick,
    Combination, Keyword,
)
from factory.combo_generator import ComboGenerator

router = APIRouter(tags=["combinations"])


def _own(db, user, campaign_id) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


@router.get("/campaigns/{id}/combinations")
def list_combinations(
    id: int, db: Db, user: CurrentUser,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    _own(db, user, id)
    q = db.query(Combination).filter(Combination.campaign_id == id)
    if status == "pending":
        q = q.filter(Combination.used_at.is_(None))
    elif status == "used":
        q = q.filter(Combination.used_at.isnot(None))
    total = q.count()
    items = q.order_by(Combination.id).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "page": page, "per_page": per_page,
        "total": total, "total_pages": (total + per_page - 1) // per_page,
        "items": [CombinationOut.model_validate(c) for c in items],
    }


@router.get("/campaigns/{id}/combinations/preview", response_model=SeedPreview)
def preview_seed(id: int, db: Db, user: CurrentUser):
    _own(db, user, id)
    slots = db.query(CampaignSlot).filter(
        CampaignSlot.campaign_id == id
    ).order_by(CampaignSlot.sort_order).all()
    by_category: dict[str, int] = {}
    total = 1
    for slot in slots:
        picks = db.query(CampaignKeywordPick).filter(
            CampaignKeywordPick.campaign_id == id,
            CampaignKeywordPick.category_id == slot.category_id,
        ).count()
        cat_name = slot.category.slug if slot.category else str(slot.category_id)
        by_category[cat_name] = picks
        if picks > 0:
            total *= picks
    return SeedPreview(total=total if slots else 0, by_category=by_category)


@router.post("/campaigns/{id}/combinations/seed", response_model=SeedResult)
def seed_combinations(id: int, db: Db, user: CurrentUser):
    _own(db, user, id)
    gen = ComboGenerator(db, id)
    count = gen.run()
    db.commit()
    return SeedResult(created=count)


@router.post("/campaigns/{id}/combinations/clear", response_model=ClearResult)
def clear_combinations(id: int, db: Db, user: CurrentUser):
    _own(db, user, id)
    deleted = db.query(Combination).filter(
        Combination.campaign_id == id,
        Combination.used_at.is_(None),
    ).delete()
    db.commit()
    return ClearResult(deleted=deleted)
