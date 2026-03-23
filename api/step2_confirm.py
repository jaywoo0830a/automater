"""api/step2_confirm.py — Step 2 Confirm: create campaign."""
from __future__ import annotations
from functools import reduce
from operator import mul
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import FriendlyError, Step2ConfirmInput, Step2ConfirmResult
from factory.models import (Campaign, CampaignAffixOverride, CampaignKeywordPick,
    CampaignPalette, CampaignSlot, KeywordCategory, Platform, SpacingRule, TemplateToken)

router = APIRouter(prefix="/step2", tags=["step-2-confirm"])

@router.post("/confirm", response_model=Step2ConfirmResult, status_code=201)
def confirm_step2(body: Step2ConfirmInput, user: CurrentUser, db: DbSession):
    platform = db.get(Platform, body.platform_id)
    if platform is None:
        raise HTTPException(status_code=422, detail=FriendlyError(
            message="Platform not found.", suggestion="Choose a valid platform.").model_dump())

    campaign = Campaign(user_id=user.id, platform_id=body.platform_id, name=body.campaign_name, status="active")
    db.add(campaign); db.flush()

    # TemplateTokens + CampaignSlots
    for ti in body.title_tokens:
        token = TemplateToken(campaign_id=campaign.id, slug=ti.slug, token_type=ti.type,
            value=ti.value if ti.type == "literal" else None, sort_order=ti.sort_order)
        db.add(token); db.flush()
        if ti.type == "keyword":
            cat = db.scalars(select(KeywordCategory).where(KeywordCategory.slug == ti.slug)).first()
            if cat: db.add(CampaignSlot(token_id=token.id, category_id=cat.id))
        if ti.type == "pool":
            existing = db.scalars(select(CampaignPalette).join(CampaignPalette.token).where(
                TemplateToken.slug == ti.slug)).first()
            if existing is None:
                db.add(CampaignPalette(token_id=token.id, strategy="random"))

    # CampaignKeywordPicks
    for sel in body.keyword_selections:
        cat = db.scalars(select(KeywordCategory).where(KeywordCategory.slug == sel.slug)).first()
        if cat is None: continue
        for kid in sel.keyword_ids:
            db.add(CampaignKeywordPick(campaign_id=campaign.id, category_id=cat.id, keyword_id=kid))

    # SpacingRules
    for style in body.spacing_styles:
        db.add(SpacingRule(campaign_id=campaign.id, pattern=style.pattern, description=style.name, active=True))

    # AffixOverrides
    for ao in body.affix_overrides:
        db.add(CampaignAffixOverride(campaign_id=campaign.id, keyword_id=ao.keyword_id,
                                     affix_id=ao.affix_id, active=ao.active))

    db.commit()

    kw_counts = [max(len(s.keyword_ids), 1) for s in body.keyword_selections]
    kw_product = reduce(mul, kw_counts, 1) if kw_counts else 0
    total = kw_product * len(body.spacing_styles)
    template = _template_str(sorted(body.title_tokens, key=lambda t: t.sort_order))

    return Step2ConfirmResult(success=True, campaign_id=campaign.id, title_template=template,
        spacing_style_count=len(body.spacing_styles), combination_count=total,
        message=f"Campaign created. {total} combinations ({kw_product} keywords x {len(body.spacing_styles)} spacing).")

def _template_str(tokens):
    parts = [t.value if t.type == "literal" else f"{{{t.slug}}}" for t in tokens]
    return " ".join(parts)
