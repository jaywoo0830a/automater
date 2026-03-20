"""
api/routes/platforms.py — listPlatforms
"""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import Db
from api.schemas import PlatformOut
from factory.models import Platform

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.get("", response_model=list[PlatformOut])
def list_platforms(db: Db):
    return db.query(Platform).all()
