"""
api/deps.py — FastAPI dependency injection.
"""
from __future__ import annotations
import os
from typing import Annotated, Generator
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from factory.db import get_engine
from factory.models import User

_JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
_JWT_ALGORITHM = "HS256"
_bearer = HTTPBearer()
_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine

def get_db() -> Generator[Session, None, None]:
    engine = _get_engine()
    with Session(engine) as session:
        yield session

def create_token(user_id: int, email: str) -> str:
    return jwt.encode({"sub": user_id, "email": email}, _JWT_SECRET, algorithm=_JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])

def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")
    user = db.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
