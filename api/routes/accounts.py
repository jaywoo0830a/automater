"""
api/routes/accounts.py — listAccounts, createAccount, getAccount, updateAccount, deleteAccount
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.deps import Db, CurrentUser, hash_password
from api.schemas import AccountCreate, AccountUpdate, AccountOut
from factory.models import Account

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _own(db, user, account_id) -> Account:
    acc = db.get(Account, account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Db, user: CurrentUser,
    platform_id: int | None = None,
    status: str | None = None,
):
    q = db.query(Account).filter(Account.user_id == user.id)
    if platform_id:
        q = q.filter(Account.platform_id == platform_id)
    if status:
        q = q.filter(Account.status == status)
    return q.all()


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, db: Db, user: CurrentUser):
    acc = Account(
        user_id=user.id,
        platform_id=body.platform_id,
        username=body.username,
        password_enc=body.password,
        extra=body.meta or {},
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.get("/{id}", response_model=AccountOut)
def get_account(id: int, db: Db, user: CurrentUser):
    return _own(db, user, id)


@router.patch("/{id}", response_model=AccountOut)
def update_account(id: int, body: AccountUpdate, db: Db, user: CurrentUser):
    acc = _own(db, user, id)
    if "password" in body.model_fields_set:
        acc.password_enc = body.password
    if "meta" in body.model_fields_set:
        acc.extra = body.meta
    for field in ("cooldown_days", "status", "note"):
        if field in body.model_fields_set:
            setattr(acc, field, getattr(body, field))
    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/{id}", status_code=204)
def delete_account(id: int, db: Db, user: CurrentUser):
    acc = _own(db, user, id)
    db.delete(acc)
    db.commit()
