"""
api/routes/presets.py — PublishPreset (5) + RunPreset (5) = 10 operations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.deps import Db, CurrentUser
from api.schemas import PresetCreate, PresetUpdate, PublishPresetOut, RunPresetOut
from factory.models import PublishPreset, RunPreset

router = APIRouter(tags=["presets"])


def _own_publish(db, user, preset_id) -> PublishPreset:
    p = db.get(PublishPreset, preset_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Publish preset not found")
    return p


def _own_run(db, user, preset_id) -> RunPreset:
    p = db.get(RunPreset, preset_id)
    if not p or p.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run preset not found")
    return p


# ---------------------------------------------------------------------------
# Publish Presets
# ---------------------------------------------------------------------------

@router.get("/publish-presets", response_model=list[PublishPresetOut])
def list_publish_presets(db: Db, user: CurrentUser):
    return db.query(PublishPreset).filter(PublishPreset.user_id == user.id).all()


@router.post("/publish-presets", response_model=PublishPresetOut, status_code=201)
def create_publish_preset(body: PresetCreate, db: Db, user: CurrentUser):
    p = PublishPreset(user_id=user.id, name=body.name, description=body.description, config=body.config)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/publish-presets/{id}", response_model=PublishPresetOut)
def get_publish_preset(id: int, db: Db, user: CurrentUser):
    return _own_publish(db, user, id)


@router.patch("/publish-presets/{id}", response_model=PublishPresetOut)
def update_publish_preset(id: int, body: PresetUpdate, db: Db, user: CurrentUser):
    p = _own_publish(db, user, id)
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.config is not None:
        p.config = body.config
    db.commit()
    db.refresh(p)
    return p


@router.delete("/publish-presets/{id}", status_code=204)
def delete_publish_preset(id: int, db: Db, user: CurrentUser):
    p = _own_publish(db, user, id)
    db.delete(p)
    db.commit()


# ---------------------------------------------------------------------------
# Run Presets
# ---------------------------------------------------------------------------

@router.get("/run-presets", response_model=list[RunPresetOut])
def list_run_presets(db: Db, user: CurrentUser):
    return db.query(RunPreset).filter(RunPreset.user_id == user.id).all()


@router.post("/run-presets", response_model=RunPresetOut, status_code=201)
def create_run_preset(body: PresetCreate, db: Db, user: CurrentUser):
    p = RunPreset(user_id=user.id, name=body.name, description=body.description, config=body.config)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/run-presets/{id}", response_model=RunPresetOut)
def get_run_preset(id: int, db: Db, user: CurrentUser):
    return _own_run(db, user, id)


@router.patch("/run-presets/{id}", response_model=RunPresetOut)
def update_run_preset(id: int, body: PresetUpdate, db: Db, user: CurrentUser):
    p = _own_run(db, user, id)
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.config is not None:
        p.config = body.config
    db.commit()
    db.refresh(p)
    return p


@router.delete("/run-presets/{id}", status_code=204)
def delete_run_preset(id: int, db: Db, user: CurrentUser):
    p = _own_run(db, user, id)
    db.delete(p)
    db.commit()
