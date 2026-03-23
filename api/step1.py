"""api/step1.py — Step 1: Account upload, confirm, list, select."""
from __future__ import annotations
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import (AccountConfirmInput, AccountConfirmResult, AccountRowPreview,
                         AccountSelectInput, AccountUploadPreview, AccountView, FriendlyError)
from factory.account_parser import parse_account_excel, validate_account_rows
from factory.models import Account, Platform

router = APIRouter(prefix="/step1/accounts", tags=["step-1-accounts"])
KST = timezone(timedelta(hours=9))

@router.post("/upload", response_model=AccountUploadPreview)
def upload_account_excel(file: UploadFile, user: CurrentUser):
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(file.file.read()); tmp_path = tmp.name
    try:
        rows = parse_account_excel(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=FriendlyError(message="Excel file could not be read.", suggestion=str(exc)).model_dump())
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    errors = validate_account_rows(rows)
    error_map = {e.row_number: e.message for e in errors}
    previews = [AccountRowPreview(row_number=r.row_number, username=r.username, platform=r.platform,
                blog_id=r.blog_id, valid=r.row_number not in error_map, error=error_map.get(r.row_number)) for r in rows]
    valid = sum(1 for p in previews if p.valid)
    return AccountUploadPreview(success=True, rows=previews, valid_count=valid, invalid_count=len(previews)-valid)

@router.post("/confirm", response_model=AccountConfirmResult)
def confirm_accounts(body: AccountConfirmInput, user: CurrentUser, db: DbSession):
    selected_indices = set(body.selected); saved = 0
    for i, ad in enumerate(body.accounts):
        platform = db.scalars(select(Platform).where(Platform.slug == ad.platform)).first()
        if platform is None:
            platform = Platform(name=ad.platform, slug=ad.platform); db.add(platform); db.flush()
        existing = db.scalars(select(Account).where(
            Account.user_id == user.id, Account.platform_id == platform.id, Account.username == ad.username)).first()
        if existing is None:
            db.add(Account(user_id=user.id, platform_id=platform.id, username=ad.username,
                password_enc=ad.password, extra={"blog_id": ad.blog_id} if ad.blog_id else {},
                cooldown_days=ad.cooldown_days, status="active" if i in selected_indices else "disabled"))
            saved += 1
        else:
            existing.password_enc = ad.password; existing.cooldown_days = ad.cooldown_days
            existing.status = "active" if i in selected_indices else "disabled"
    db.commit()
    return AccountConfirmResult(success=True, message=f"{saved} saved. {len(selected_indices)} selected.",
                                saved_count=saved, selected_count=len(selected_indices))

@router.get("", response_model=list[AccountView])
def list_accounts(user: CurrentUser, db: DbSession):
    now = datetime.now(tz=KST)
    return [AccountView(id=a.id, username=a.username,
            platform=a.platform.slug if a.platform else "",
            status=_status(a, now), selected=a.status == "active",
            last_used=_rel(a.last_used_at, now) if a.last_used_at else None)
            for a in db.scalars(select(Account).where(Account.user_id == user.id)).all()]

@router.put("/select", response_model=AccountConfirmResult)
def select_accounts(body: AccountSelectInput, user: CurrentUser, db: DbSession):
    ids = set(body.account_ids)
    for a in db.scalars(select(Account).where(Account.user_id == user.id)).all():
        if a.id in ids: a.status = "active"
        elif a.status == "active": a.status = "disabled"
    db.commit()
    return AccountConfirmResult(success=True, message=f"{len(ids)} selected.", saved_count=0, selected_count=len(ids))

def _status(a, now):
    if a.status == "disabled": return "Disabled"
    if a.status == "cooling" and a.last_used_at:
        last = a.last_used_at.replace(tzinfo=KST) if a.last_used_at.tzinfo is None else a.last_used_at
        rem = (last + timedelta(days=a.cooldown_days) - now).days
        if rem > 0: return f"Cooling ({rem} days left)"
    return "Ready"

def _rel(dt, now):
    if dt.tzinfo is None: dt = dt.replace(tzinfo=KST)
    d = (now - dt).days
    return f"{d} days ago" if d > 0 else "today"
