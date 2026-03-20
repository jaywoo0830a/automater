"""
api/routes/layouts.py — listLayouts, createLayout, getLayout, updateLayout,
                         deleteLayout, replaceSlots, previewLayout
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import Db, CurrentUser
from api.schemas import (
    LayoutCreate, LayoutUpdate, LayoutOut, LayoutSlotIn, LayoutSlotOut,
    PreviewRequest, RenderedBlock,
)
from automator.block_factory import create_block, _interpolate, FACTORIES
from factory.models import PostLayout, LayoutSlot

router = APIRouter(prefix="/layouts", tags=["layouts"])


def _own(db, user, layout_id) -> PostLayout:
    layout = db.get(PostLayout, layout_id)
    if not layout or layout.user_id != user.id:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


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
    if body.name is not None:
        layout.name = body.name
    if body.description is not None:
        layout.description = body.description
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
    result = []
    for slot in sorted(layout.slots, key=lambda s: s.sort_order):
        config = dict(slot.config) if slot.config else {}
        rendered = _interpolate(config, body.values, keyword)
        result.append(RenderedBlock(block_type=slot.block_type, rendered_config=rendered))
    return result
