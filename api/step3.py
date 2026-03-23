"""api/step3.py — Step 3: Post template selection."""
from __future__ import annotations
import random
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (BlockDetail, PostBlockPreview, PostPreview, TemplateDetailView, TemplateView)
from automator.title_generator import generate_title
from automator.options import TitleOption
from factory.job_builder import _build_template, _build_values, _build_pools
from factory.models import Campaign, Combination, PostLayout

router = APIRouter(prefix="/step3/templates", tags=["step-3-templates"])

_ABBR = {"heading":"H2","paragraph":"P","image":"IMG","featured":"FEATURED","list":"LIST","quote":"Q","divider":"---"}

@router.get("", response_model=list[TemplateView])
def list_templates(user: CurrentUser, db: DbSession):
    layouts = db.scalars(select(PostLayout).where(PostLayout.user_id == user.id)).all()
    return [TemplateView(id=l.id, name=l.name, description=l.description or "",
        block_summary=" → ".join(_ABBR.get(s.block_type, s.block_type.upper())
            for s in sorted(l.slots, key=lambda s: s.sort_order))) for l in layouts]

@router.get("/{template_id}", response_model=TemplateDetailView)
def get_template(template_id: int, user: CurrentUser, db: DbSession):
    layout = db.get(PostLayout, template_id)
    if layout is None: raise HTTPException(status_code=404, detail="Template not found.")
    return TemplateDetailView(id=layout.id, name=layout.name, description=layout.description or "",
        blocks=[BlockDetail(order=s.sort_order, type=s.block_type,
            label=(s.config or {}).get("label", s.block_type),
            config_summary=_cfg(s.config)) for s in sorted(layout.slots, key=lambda s: s.sort_order)])

@router.get("/{template_id}/preview", response_model=PostPreview)
def preview_template(template_id: int, user: CurrentUser, db: DbSession, campaign_id: int = 0):
    layout = db.get(PostLayout, template_id)
    if layout is None: raise HTTPException(status_code=404, detail="Template not found.")
    title = "[Sample Title]"; kw_str = ""
    if campaign_id:
        campaign = db.get(Campaign, campaign_id)
        if campaign:
            tmpl = _build_template(campaign); pools = _build_pools(campaign)
            combo = db.scalars(select(Combination).where(Combination.campaign_id == campaign_id)).first()
            if combo:
                vals = _build_values(combo); kw_str = " ".join(vals.values())
                try: title = generate_title(TitleOption(template=tmpl, values=vals, pools=pools, seed=42), rng=random.Random(42))
                except (ValueError, KeyError): title = tmpl
            else: title = tmpl
    blocks = [PostBlockPreview(type=s.block_type, placeholder=_ph(s.block_type, kw_str))
              for s in sorted(layout.slots, key=lambda s: s.sort_order)]
    return PostPreview(sample_title=title, blocks=blocks)

def _cfg(c):
    if not c: return None
    parts = []
    if c.get("min_chars"): parts.append(f"min {c['min_chars']} chars")
    if c.get("tone"): parts.append(c["tone"])
    if c.get("level"): parts.append(f"level {c['level']}")
    return ", ".join(parts) if parts else None

def _ph(bt, kw):
    if bt == "heading": return kw or "[Heading]"
    if bt == "paragraph": return f"[AI paragraph{' about '+kw if kw else ''}]"
    if bt == "image": return "[Body image]"
    if bt == "featured": return "[Thumbnail]"
    return f"[{bt}]"
