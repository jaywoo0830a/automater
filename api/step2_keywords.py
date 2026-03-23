"""api/step2_keywords.py — Step 2a: Keywords + Affix control."""
from __future__ import annotations
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (AffixInfo, AffixOverrideInput, AffixOverrideResult,
    CategoryPreview, FriendlyError, KeywordAddInput, KeywordCategoryView,
    KeywordEditInput, KeywordImportInput, KeywordImportResult, KeywordItem,
    KeywordUploadPreview)
from factory.excel_parser import parse_excel
from factory.affix_detector import detect_affixes
from factory.models import Affix, CampaignAffixOverride, Keyword, KeywordCategory

router = APIRouter(prefix="/step2/keywords", tags=["step-2-keywords"])

# -- Upload (preview) --------------------------------------------------------
@router.post("/upload", response_model=KeywordUploadPreview)
def upload_keyword_excel(file: UploadFile, user: CurrentUser):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file.file.read()); tmp_path = tmp.name
    try:
        data = parse_excel(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=FriendlyError(message="Excel could not be read.", suggestion=str(exc)).model_dump())
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    cats = []; total = 0
    for col, vals in data.items():
        detected = detect_affixes(vals) if vals else []
        affix_strs = [f"{a[0]}: {a[1]}" for a in detected] if detected and isinstance(detected[0], tuple) else [str(a) for a in detected]
        cats.append(CategoryPreview(column_name=col, slug=col.lower().replace(" ", "_"),
            keyword_count=len(vals), sample_values=vals[:5], detected_affixes=affix_strs))
        total += len(vals)
    return KeywordUploadPreview(success=True, categories=cats, total_keywords=total)

# -- Import (save + auto affix link) -----------------------------------------
@router.post("/import", response_model=KeywordImportResult)
def import_keywords(body: KeywordImportInput, user: CurrentUser, db: DbSession):
    cats_created = kw_created = kw_existing = affixes_linked = 0
    for ci in body.categories:
        cat = db.scalars(select(KeywordCategory).where(KeywordCategory.slug == ci.slug)).first()
        if cat is None:
            cat = KeywordCategory(name=ci.name or ci.slug, slug=ci.slug); db.add(cat); db.flush(); cats_created += 1
        for val in ci.values:
            val = val.strip()
            existing = db.scalars(select(Keyword).where(Keyword.category_id == cat.id, Keyword.value == val)).first()
            if existing:
                kw_existing += 1; continue
            kw = Keyword(category_id=cat.id, value=val, display_value="", active=True)
            db.add(kw); db.flush(); kw_created += 1
            if body.auto_detect_affixes:
                affixes_linked += _link_affixes(db, kw)
    db.commit()
    return KeywordImportResult(success=True, categories_created=cats_created, keywords_created=kw_created,
        keywords_existing=kw_existing, affixes_linked=affixes_linked,
        message=f"{cats_created} categories, {kw_created} keywords imported. {affixes_linked} affixes linked.")

# -- List categories (with keywords + affixes) --------------------------------
@router.get("/categories", response_model=list[KeywordCategoryView])
def list_categories(user: CurrentUser, db: DbSession):
    cats = db.scalars(select(KeywordCategory).order_by(KeywordCategory.id)).all()
    return [KeywordCategoryView(slug=c.slug, name=c.name,
        keywords=[_kw_to_item(kw) for kw in sorted(c.keywords, key=lambda k: k.sort_order)]) for c in cats]

# -- Add keyword --------------------------------------------------------------
@router.post("/categories/{slug}", response_model=KeywordItem, status_code=201)
def add_keyword(slug: str, body: KeywordAddInput, user: CurrentUser, db: DbSession):
    cat = db.scalars(select(KeywordCategory).where(KeywordCategory.slug == slug)).first()
    if cat is None:
        cat = KeywordCategory(name=slug, slug=slug); db.add(cat); db.flush()
    kw = Keyword(category_id=cat.id, value=body.value.strip(), display_value="", active=True)
    db.add(kw); db.flush()
    _link_affixes(db, kw)
    db.commit()
    return _kw_to_item(kw)

# -- Edit keyword -------------------------------------------------------------
@router.put("/{keyword_id}", response_model=KeywordItem)
def edit_keyword(keyword_id: int, body: KeywordEditInput, user: CurrentUser, db: DbSession):
    kw = db.get(Keyword, keyword_id)
    if kw is None: raise HTTPException(status_code=404, detail="Keyword not found.")
    if body.value is not None: kw.value = body.value.strip()
    if body.active is not None: kw.active = body.active
    db.commit()
    return _kw_to_item(kw)

# -- Delete keyword -----------------------------------------------------------
@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, user: CurrentUser, db: DbSession):
    kw = db.get(Keyword, keyword_id)
    if kw is None: raise HTTPException(status_code=404, detail="Keyword not found.")
    db.delete(kw); db.commit()

# -- Affix overrides ----------------------------------------------------------
@router.put("/affix-overrides", response_model=AffixOverrideResult)
def set_affix_overrides(body: AffixOverrideInput, user: CurrentUser, db: DbSession):
    count = 0
    for entry in body.overrides:
        existing = db.scalars(select(CampaignAffixOverride).where(
            CampaignAffixOverride.keyword_id == entry.keyword_id,
            CampaignAffixOverride.affix_id == entry.affix_id,
        )).first()
        if existing:
            existing.active = entry.active
        else:
            db.add(CampaignAffixOverride(campaign_id=0, keyword_id=entry.keyword_id,
                affix_id=entry.affix_id, active=entry.active))
        count += 1
    db.commit()
    return AffixOverrideResult(success=True, message=f"{count} overrides updated.", updated_count=count)

# -- Helpers ------------------------------------------------------------------
def _kw_to_item(kw: Keyword) -> KeywordItem:
    affixes = []
    for affix in getattr(kw, "affixes", []):
        stripped = kw.value
        if affix.type == "suffix" and kw.value.endswith(affix.value):
            stripped = kw.value[:-len(affix.value)]
        elif affix.type == "prefix" and kw.value.startswith(affix.value):
            stripped = kw.value[len(affix.value):]
        affixes.append(AffixInfo(affix_id=affix.id, type=affix.type, value=affix.value,
            active=True, stripped_result=stripped))
    return KeywordItem(id=kw.id, value=kw.value, display_value=kw.display_value or "",
                       active=kw.active, affixes=affixes)

def _link_affixes(db, kw: Keyword) -> int:
    from factory.affix_detector import DEFAULT_SUFFIXES
    linked = 0
    for suffix_val in DEFAULT_SUFFIXES:
        if kw.value.endswith(suffix_val):
            affix = db.scalars(select(Affix).where(Affix.type == "suffix", Affix.value == suffix_val)).first()
            if affix is None:
                affix = Affix(type="suffix", value=suffix_val); db.add(affix); db.flush()
            if affix not in kw.affixes:
                kw.affixes.append(affix); linked += 1
    return linked
