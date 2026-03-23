"""api/auth.py — POST /auth/login"""
from __future__ import annotations
from hashlib import sha256
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from api.deps import DbSession, create_token
from api.schemas import FriendlyError, LoginRequest, LoginResponse, LoginUser
from factory.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: DbSession):
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if user is None or sha256(body.password.encode()).hexdigest() != user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=FriendlyError(
            message="Email or password is incorrect.",
            suggestion="Check your email spelling.",
        ).model_dump())
    return LoginResponse(token=create_token(user.id, user.email),
                         user=LoginUser(display_name=user.display_name, email=user.email))
