"""
api/routes/layouts.py — listLayouts, createLayout, getLayout, updateLayout,
                         deleteLayout, replaceSlots, previewLayout
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.deps import Db, CurrentUser
from api.schemas import (
    LayoutCreate, LayoutUpdate, LayoutOut, LayoutSlotIn, LayoutSlotOut,
    PreviewRequest, RenderedBlock,
)
from automator.block_factory import _interpolate, _resolve_media, FACTORIES
from factory.models import PostLayout, LayoutSlot, Media
from factory.storage import LocalStorage

router = APIRouter(prefix="/layouts", tags=["layouts"])

MEDIA_DIR = Path(os.getenv("MEDIA_STORAGE_DIR", "uploads"))


def _own(db, user, layout_id) -> PostLayout:
    layout = db.get(PostLayout, layout_id)
    if not layout or layout.user_id != user.id:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


def _media_resolver(db, storage):
    """Build a media_id → path resolver for preview."""
    def resolve(media_id: int) -> str:
        m = db.get(Media, media_id)
        if not m:
            return f"[media:{media_id} not found]"
        return str(storage.resolve(m.storage_path))
    return resolve


@router.get("", response_model=list[LayoutOut])
def list_layouts(db: Db, user: CurrentUser):
    return db.query(PostLayout).filter(PostLayout.user_id == user.id).all()


@router.post("", response_model=LayoutOut, status_code=201)
def create_layout(body: LayoutCreate, db: Db, user: CurrentUser):
    layout = PostLayout(user_id=user.id, name=body.name, description=body.description)
    db.add(layout)
    db.flush()
    for s in body.slots:
        db.add(LayoutSlot(
            layout_id=layout.id, sort_order=s.sort_order,
            block_type=s.block_type, config=s.config,
        ))
    db.commit()
    db.refresh(layout)
    return layout


@router.get("/{id}", response_model=LayoutOut)
def get_layout(id: int, db: Db, user: CurrentUser):
    return _own(db, user, id)


@router.patch("/{id}", response_model=LayoutOut)
def update_layout(id: int, body: LayoutUpdate, db: Db, user: CurrentUser):
    layout = _own(db, user, id)
    for field in ("name", "description"):
        if field in body.model_fields_set:
            setattr(layout, field, getattr(body, field))
    db.commit()
    db.refresh(layout)
    return layout


@router.delete("/{id}", status_code=204)
def delete_layout(id: int, db: Db, user: CurrentUser):
    layout = _own(db, user, id)
    db.delete(layout)
    db.commit()


@router.put("/{id}/slots", response_model=list[LayoutSlotOut])
def replace_slots(id: int, slots: list[LayoutSlotIn], db: Db, user: CurrentUser):
    layout = _own(db, user, id)
    db.query(LayoutSlot).filter(LayoutSlot.layout_id == layout.id).delete()
    new_slots = []
    for s in slots:
        slot = LayoutSlot(
            layout_id=layout.id, sort_order=s.sort_order,
            block_type=s.block_type, config=s.config,
        )
        db.add(slot)
        new_slots.append(slot)
    db.commit()
    for s in new_slots:
        db.refresh(s)
    return new_slots


@router.post("/{id}/preview", response_model=list[RenderedBlock])
def preview_layout(id: int, body: PreviewRequest, db: Db, user: CurrentUser):
    layout = _own(db, user, id)
    keyword = " ".join(body.values.values()) if body.values else ""
    storage = LocalStorage(base_dir=MEDIA_DIR)
    resolver = _media_resolver(db, storage)

    result = []
    for slot in sorted(layout.slots, key=lambda s: s.sort_order):
        config = dict(slot.config) if slot.config else {}
        config = _resolve_media(config, slot.block_type, resolver)
        rendered = _interpolate(config, body.values, keyword)
        result.append(RenderedBlock(block_type=slot.block_type, rendered_config=rendered))
    return result
