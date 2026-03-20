"""
api/routes/admin.py — listUsers, getUser, updateUser
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.deps import Db, AdminUser
from api.schemas import UserOut, AdminUserUpdate
from factory.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(db: Db, _: AdminUser, page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)):
    total = db.query(User).count()
    users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "page": page, "per_page": per_page,
        "total": total, "total_pages": (total + per_page - 1) // per_page,
        "items": [UserOut.model_validate(u) for u in users],
    }


@router.get("/users/{id}", response_model=UserOut)
def get_user(id: int, db: Db, _: AdminUser):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{id}", response_model=UserOut)
def update_user(id: int, body: AdminUserUpdate, db: Db, _: AdminUser):
    user = db.get(User, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field in ("role", "status"):
        if field in body.model_fields_set:
            setattr(user, field, getattr(body, field))
    db.commit()
    db.refresh(user)
    return user
