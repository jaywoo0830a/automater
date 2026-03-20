"""
api/routes/keywords.py — categories (4), keywords (4), affixes (5) = 13 operations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.deps import Db, CurrentUser
from api.schemas import (
    CategoryCreate, CategoryUpdate, CategoryOut,
    KeywordCreate, KeywordUpdate, KeywordOut,
    AffixCreate, AffixUpdate, AffixOut,
)
from factory.models import KeywordCategory, Keyword, Affix

router = APIRouter(tags=["keywords"])


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/keyword-categories", response_model=list[CategoryOut])
def list_categories(db: Db, _: CurrentUser):
    return db.query(KeywordCategory).order_by(KeywordCategory.name).all()


@router.post("/keyword-categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, db: Db, _: CurrentUser):
    cat = KeywordCategory(name=body.name, slug=body.slug)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/keyword-categories/{id}", response_model=CategoryOut)
def update_category(id: int, body: CategoryUpdate, db: Db, _: CurrentUser):
    cat = db.get(KeywordCategory, id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.name is not None:
        cat.name = body.name
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/keyword-categories/{id}", status_code=204)
def delete_category(id: int, db: Db, _: CurrentUser):
    cat = db.get(KeywordCategory, id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

def _build_tree(keywords: list[Keyword]) -> list[Keyword]:
    """Nest children under parents for tree response."""
    by_id = {kw.id: kw for kw in keywords}
    roots = []
    for kw in keywords:
        if kw.parent_id and kw.parent_id in by_id:
            pass  # SQLAlchemy relationship handles nesting
        else:
            roots.append(kw)
    return roots


@router.get("/keyword-categories/{id}/keywords", response_model=list[KeywordOut])
def list_keywords(
    id: int, db: Db, _: CurrentUser,
    tree: bool = False,
    active: bool | None = None,
):
    q = db.query(Keyword).filter(Keyword.category_id == id).order_by(Keyword.sort_order)
    if active is not None:
        q = q.filter(Keyword.active == active)
    keywords = q.all()
    if tree:
        return _build_tree(keywords)
    return keywords


@router.post("/keyword-categories/{id}/keywords", response_model=KeywordOut, status_code=201)
def create_keyword(id: int, body: KeywordCreate, db: Db, _: CurrentUser):
    cat = db.get(KeywordCategory, id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    kw = Keyword(
        category_id=id,
        value=body.value,
        display_value=body.display_value or body.value,
        parent_id=body.parent_id,
        tier=body.tier,
        metadata_=body.metadata,
    )
    db.add(kw)
    db.commit()
    db.refresh(kw)
    return kw


@router.get("/keywords/{id}", response_model=KeywordOut)
def get_keyword(id: int, db: Db, _: CurrentUser):
    kw = db.get(Keyword, id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return kw


@router.patch("/keywords/{id}", response_model=KeywordOut)
def update_keyword(id: int, body: KeywordUpdate, db: Db, _: CurrentUser):
    kw = db.get(Keyword, id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    for field in ("value", "display_value", "parent_id", "tier", "active", "sort_order"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(kw, field, val)
    if body.metadata is not None:
        kw.metadata_ = body.metadata
    db.commit()
    db.refresh(kw)
    return kw


@router.delete("/keywords/{id}", status_code=204)
def delete_keyword(id: int, db: Db, _: CurrentUser):
    kw = db.get(Keyword, id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(kw)
    db.commit()


# ---------------------------------------------------------------------------
# Affixes
# ---------------------------------------------------------------------------

@router.get("/keywords/{id}/affixes", response_model=list[AffixOut])
def list_affixes(id: int, db: Db, _: CurrentUser):
    return db.query(Affix).filter(Affix.keyword_id == id).order_by(Affix.sort_order).all()


@router.post("/keywords/{id}/affixes", response_model=AffixOut, status_code=201)
def create_affix(id: int, body: AffixCreate, db: Db, _: CurrentUser):
    kw = db.get(Keyword, id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    affix = Affix(keyword_id=id, type=body.type, value=body.value, sort_order=body.sort_order)
    db.add(affix)
    db.commit()
    db.refresh(affix)
    return affix


@router.patch("/affixes/{id}", response_model=AffixOut)
def update_affix(id: int, body: AffixUpdate, db: Db, _: CurrentUser):
    affix = db.get(Affix, id)
    if not affix:
        raise HTTPException(status_code=404, detail="Affix not found")
    for field in ("value", "sort_order", "active"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(affix, field, val)
    db.commit()
    db.refresh(affix)
    return affix


@router.delete("/affixes/{id}", status_code=204)
def delete_affix(id: int, db: Db, _: CurrentUser):
    affix = db.get(Affix, id)
    if not affix:
        raise HTTPException(status_code=404, detail="Affix not found")
    db.delete(affix)
    db.commit()
