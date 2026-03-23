"""api/step2_pools.py — Step 2b: Pool upload, browse, CRUD."""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (FriendlyError, PoolCreatedInfo, PoolItemAddInput, PoolItemEditInput,
                         PoolItemView, PoolUploadResult, PoolView)
from factory.excel_parser import parse_excel
from factory.models import CampaignPalette, PaletteItem, TemplateToken

router = APIRouter(prefix="/step2/pools", tags=["step-2-pools"])

@router.post("/upload", response_model=PoolUploadResult)
def upload_pool_excel(file: UploadFile, user: CurrentUser, db: DbSession):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file.file.read()); tmp_path = tmp.name
    try:
        data = parse_excel(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=FriendlyError(message="Excel could not be read.", suggestion=str(exc)).model_dump())
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    infos = []
    for slug_raw, vals in data.items():
        slug = slug_raw.lower().strip().replace(" ", "_")
        palette = _get_or_create_palette(db, slug)
        existing_vals = {i.value for i in palette.items}
        mx = max((i.sort_order for i in palette.items), default=-1)
        created = 0
        for v in vals:
            v = v.strip()
            if v and v not in existing_vals:
                mx += 1; db.add(PaletteItem(palette_id=palette.token_id, value=v, sort_order=mx, active=True))
                existing_vals.add(v); created += 1
        infos.append(PoolCreatedInfo(slug=slug, created_count=created, samples=vals[:3]))
    db.commit()
    return PoolUploadResult(success=True, message=f"{len(infos)} pools imported.", pools=infos)

@router.get("", response_model=list[PoolView])
def list_pools(user: CurrentUser, db: DbSession):
    palettes = db.scalars(select(CampaignPalette)).all()
    return [PoolView(slug=p.token.slug if p.token else str(p.token_id), strategy=p.strategy,
        items=[PoolItemView(id=i.id, value=i.value, active=i.active, sort_order=i.sort_order)
               for i in sorted(p.items, key=lambda x: x.sort_order)]) for p in palettes]

@router.post("/{slug}/items", response_model=PoolItemView, status_code=201)
def add_pool_item(slug: str, body: PoolItemAddInput, user: CurrentUser, db: DbSession):
    palette = _get_or_create_palette(db, slug)
    mx = max((i.sort_order for i in palette.items), default=-1)
    item = PaletteItem(palette_id=palette.token_id, value=body.value.strip(), sort_order=mx+1, active=True)
    db.add(item); db.commit()
    return PoolItemView(id=item.id, value=item.value, active=item.active, sort_order=item.sort_order)

@router.put("/{slug}/items/{item_id}", response_model=PoolItemView)
def edit_pool_item(slug: str, item_id: int, body: PoolItemEditInput, user: CurrentUser, db: DbSession):
    item = db.get(PaletteItem, item_id)
    if item is None: raise HTTPException(status_code=404, detail="Pool item not found.")
    if body.value is not None: item.value = body.value.strip()
    if body.active is not None: item.active = body.active
    db.commit()
    return PoolItemView(id=item.id, value=item.value, active=item.active, sort_order=item.sort_order)

@router.delete("/{slug}/items/{item_id}", status_code=204)
def delete_pool_item(slug: str, item_id: int, user: CurrentUser, db: DbSession):
    item = db.get(PaletteItem, item_id)
    if item is None: raise HTTPException(status_code=404, detail="Pool item not found.")
    db.delete(item); db.commit()

def _get_or_create_palette(db, slug: str) -> CampaignPalette:
    token = db.scalars(select(TemplateToken).where(TemplateToken.slug == slug, TemplateToken.token_type == "pool")).first()
    if token and token.palette: return token.palette
    if token is None:
        token = TemplateToken(campaign_id=0, slug=slug, token_type="pool", sort_order=0)
        db.add(token); db.flush()
    palette = CampaignPalette(token_id=token.id, strategy="random")
    db.add(palette); db.flush()
    return palette
