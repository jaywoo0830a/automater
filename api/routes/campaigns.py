"""
api/routes/campaigns.py — 22 operations
Campaign CRUD (5) + stats + preview-title + slots (2) + picks (2) +
palettes (5) + spacing-rules (4) + clone = 22
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from api.deps import Db, CurrentUser
from api.schemas import (
    CampaignCreate, CampaignUpdate, CampaignOut, CloneRequest, CampaignStats,
    PreviewTitleRequest,
    CampaignSlotIn, CampaignSlotOut,
    PicksRequest,
    PaletteCreate, PaletteUpdate, PaletteOut, PaletteItemIn, PaletteItemOut,
    SpacingRuleCreate, SpacingRuleUpdate, SpacingRuleOut,
)
from automator.title_generator import generate_title
from automator.options import TitleOption
from factory.models import (
    Campaign, CampaignSlot, CampaignKeywordPick, CampaignPalette, PaletteItem,
    SpacingRule, Combination, Batch, BatchItem, KeywordCategory, Keyword,
)

router = APIRouter(tags=["campaigns"])


def _own_campaign(db, user, campaign_id) -> Campaign:
    c = db.query(Campaign).options(
        joinedload(Campaign.layout),
        joinedload(Campaign.publish_preset),
        joinedload(Campaign.run_preset),
    ).filter(Campaign.id == campaign_id, Campaign.user_id == user.id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


# ── Campaign CRUD ──────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    db: Db, user: CurrentUser,
    status: str | None = None,
    platform_id: int | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    q = db.query(Campaign).filter(Campaign.user_id == user.id)
    if status:
        q = q.filter(Campaign.status == status)
    if platform_id:
        q = q.filter(Campaign.platform_id == platform_id)
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "page": page, "per_page": per_page,
        "total": total, "total_pages": (total + per_page - 1) // per_page,
        "items": [CampaignOut.model_validate(c) for c in items],
    }


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignCreate, db: Db, user: CurrentUser):
    c = Campaign(
        user_id=user.id,
        platform_id=body.platform_id,
        name=body.name,
        description=body.description,
        title_template=body.title_template,
        layout_id=body.layout_id,
        publish_preset_id=body.publish_preset_id,
        run_preset_id=body.run_preset_id,
        config=body.config,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/campaigns/{id}", response_model=CampaignOut)
def get_campaign(id: int, db: Db, user: CurrentUser):
    return _own_campaign(db, user, id)


@router.patch("/campaigns/{id}", response_model=CampaignOut)
def update_campaign(id: int, body: CampaignUpdate, db: Db, user: CurrentUser):
    c = _own_campaign(db, user, id)
    for field in ("name", "description", "title_template", "layout_id",
                  "publish_preset_id", "run_preset_id", "status", "config"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/campaigns/{id}", status_code=204)
def delete_campaign(id: int, db: Db, user: CurrentUser):
    c = _own_campaign(db, user, id)
    db.delete(c)
    db.commit()


@router.post("/campaigns/{id}/clone", response_model=CampaignOut, status_code=201)
def clone_campaign(id: int, body: CloneRequest, db: Db, user: CurrentUser):
    src = _own_campaign(db, user, id)
    clone = Campaign(
        user_id=user.id,
        platform_id=src.platform_id,
        name=body.name or f"{src.name} (copy)",
        description=src.description,
        title_template=src.title_template,
        layout_id=src.layout_id,
        publish_preset_id=src.publish_preset_id,
        run_preset_id=src.run_preset_id,
        config=src.config,
    )
    db.add(clone)
    db.flush()
    for slot in src.slots:
        db.add(CampaignSlot(campaign_id=clone.id, category_id=slot.category_id, sort_order=slot.sort_order))
    for pick in src.picks:
        db.add(CampaignKeywordPick(campaign_id=clone.id, category_id=pick.category_id, keyword_id=pick.keyword_id))
    for pal in src.palettes:
        new_pal = CampaignPalette(campaign_id=clone.id, slug=pal.slug, strategy=pal.strategy)
        db.add(new_pal)
        db.flush()
        for item in pal.items:
            db.add(PaletteItem(palette_id=new_pal.id, value=item.value, sort_order=item.sort_order, active=item.active))
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/campaigns/{id}/stats", response_model=CampaignStats)
def get_campaign_stats(id: int, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    total_combos = db.query(func.count(Combination.id)).filter(Combination.campaign_id == id).scalar() or 0
    pending_combos = db.query(func.count(Combination.id)).filter(
        Combination.campaign_id == id, Combination.used_at.is_(None)
    ).scalar() or 0
    total_batches = db.query(func.count(Batch.id)).filter(Batch.campaign_id == id).scalar() or 0
    completed_batches = db.query(func.count(Batch.id)).filter(
        Batch.campaign_id == id, Batch.status == "completed"
    ).scalar() or 0
    total_items = db.query(func.count(BatchItem.id)).join(Batch).filter(Batch.campaign_id == id).scalar() or 0
    failed_items = db.query(func.count(BatchItem.id)).join(Batch).filter(
        Batch.campaign_id == id, BatchItem.status == "failed"
    ).scalar() or 0
    rate = ((total_items - failed_items) / total_items * 100) if total_items > 0 else 0.0
    return CampaignStats(
        total_combinations=total_combos, pending_combinations=pending_combos,
        total_batches=total_batches, completed_batches=completed_batches,
        failed_items=failed_items, success_rate=round(rate, 1),
    )


@router.post("/campaigns/{id}/preview-title")
def preview_title(id: int, body: PreviewTitleRequest, db: Db, user: CurrentUser):
    c = _own_campaign(db, user, id)
    opt = TitleOption(
        template=c.title_template,
        values=body.values,
        seed=body.seed,
    )
    title = generate_title(opt, rng=random.Random(body.seed) if body.seed else None)
    return {"title": title}


# ── Campaign Slots ─────────────────────────────────────────────────────────

@router.get("/campaigns/{id}/slots", response_model=list[CampaignSlotOut])
def list_campaign_slots(id: int, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    return db.query(CampaignSlot).filter(
        CampaignSlot.campaign_id == id
    ).order_by(CampaignSlot.sort_order).all()


@router.put("/campaigns/{id}/slots", response_model=list[CampaignSlotOut])
def replace_campaign_slots(id: int, slots: list[CampaignSlotIn], db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    db.query(CampaignSlot).filter(CampaignSlot.campaign_id == id).delete()
    new_slots = []
    for s in slots:
        slot = CampaignSlot(campaign_id=id, category_id=s.category_id, sort_order=s.sort_order)
        db.add(slot)
        new_slots.append(slot)
    db.commit()
    for s in new_slots:
        db.refresh(s)
    return new_slots


# ── Campaign Picks ─────────────────────────────────────────────────────────

@router.get("/campaigns/{id}/picks")
def list_picks(id: int, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    picks = db.query(CampaignKeywordPick).filter(
        CampaignKeywordPick.campaign_id == id
    ).all()
    result: dict[str, list[str]] = {}
    for p in picks:
        slug = p.category.slug
        result.setdefault(slug, []).append(p.keyword.value)
    return result


@router.put("/campaigns/{id}/picks")
def save_picks(id: int, body: PicksRequest, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    cat = db.query(KeywordCategory).filter(KeywordCategory.slug == body.category_slug).first()
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category '{body.category_slug}' not found")
    db.query(CampaignKeywordPick).filter(
        CampaignKeywordPick.campaign_id == id,
        CampaignKeywordPick.category_id == cat.id,
    ).delete()
    count = 0
    for val in body.values:
        kw = db.query(Keyword).filter(Keyword.category_id == cat.id, Keyword.value == val).first()
        if kw:
            db.add(CampaignKeywordPick(campaign_id=id, category_id=cat.id, keyword_id=kw.id))
            count += 1
    db.commit()
    return {"count": count}


# ── Palettes ───────────────────────────────────────────────────────────────

@router.get("/campaigns/{id}/palettes", response_model=list[PaletteOut])
def list_palettes(id: int, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    return db.query(CampaignPalette).filter(CampaignPalette.campaign_id == id).all()


@router.post("/campaigns/{id}/palettes", response_model=PaletteOut, status_code=201)
def create_palette(id: int, body: PaletteCreate, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    pal = CampaignPalette(campaign_id=id, slug=body.slug, strategy=body.strategy)
    db.add(pal)
    db.flush()
    for item in body.items:
        db.add(PaletteItem(palette_id=pal.id, value=item.value, sort_order=item.sort_order, active=item.active))
    db.commit()
    db.refresh(pal)
    return pal


@router.get("/palettes/{id}", response_model=PaletteOut)
def get_palette(id: int, db: Db, user: CurrentUser):
    pal = db.get(CampaignPalette, id)
    if not pal:
        raise HTTPException(status_code=404, detail="Palette not found")
    _own_campaign(db, user, pal.campaign_id)
    return pal


@router.patch("/palettes/{id}", response_model=PaletteOut)
def update_palette(id: int, body: PaletteUpdate, db: Db, user: CurrentUser):
    pal = db.get(CampaignPalette, id)
    if not pal:
        raise HTTPException(status_code=404, detail="Palette not found")
    _own_campaign(db, user, pal.campaign_id)
    if body.strategy is not None:
        pal.strategy = body.strategy
    db.commit()
    db.refresh(pal)
    return pal


@router.delete("/palettes/{id}", status_code=204)
def delete_palette(id: int, db: Db, user: CurrentUser):
    pal = db.get(CampaignPalette, id)
    if not pal:
        raise HTTPException(status_code=404, detail="Palette not found")
    _own_campaign(db, user, pal.campaign_id)
    db.delete(pal)
    db.commit()


@router.put("/palettes/{id}/items", response_model=list[PaletteItemOut])
def replace_palette_items(id: int, items: list[PaletteItemIn], db: Db, user: CurrentUser):
    pal = db.get(CampaignPalette, id)
    if not pal:
        raise HTTPException(status_code=404, detail="Palette not found")
    _own_campaign(db, user, pal.campaign_id)
    db.query(PaletteItem).filter(PaletteItem.palette_id == id).delete()
    new_items = []
    for item in items:
        pi = PaletteItem(palette_id=id, value=item.value, sort_order=item.sort_order, active=item.active)
        db.add(pi)
        new_items.append(pi)
    db.commit()
    for pi in new_items:
        db.refresh(pi)
    return new_items


# ── Spacing Rules ──────────────────────────────────────────────────────────

@router.get("/campaigns/{id}/spacing-rules", response_model=list[SpacingRuleOut])
def list_spacing_rules(id: int, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    return db.query(SpacingRule).filter(SpacingRule.campaign_id == id).all()


@router.post("/campaigns/{id}/spacing-rules", response_model=SpacingRuleOut, status_code=201)
def create_spacing_rule(id: int, body: SpacingRuleCreate, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    rule = SpacingRule(campaign_id=id, pattern=body.pattern, description=body.description, active=body.active)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/spacing-rules/{id}", response_model=SpacingRuleOut)
def update_spacing_rule(id: int, body: SpacingRuleUpdate, db: Db, user: CurrentUser):
    rule = db.get(SpacingRule, id)
    if not rule:
        raise HTTPException(status_code=404, detail="Spacing rule not found")
    _own_campaign(db, user, rule.campaign_id)
    for field in ("pattern", "description", "active"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(rule, field, val)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/spacing-rules/{id}", status_code=204)
def delete_spacing_rule(id: int, db: Db, user: CurrentUser):
    rule = db.get(SpacingRule, id)
    if not rule:
        raise HTTPException(status_code=404, detail="Spacing rule not found")
    _own_campaign(db, user, rule.campaign_id)
    db.delete(rule)
    db.commit()
