"""api/monitor.py — Monitoring: batch progress, detail, retry, stop."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from api.deps import CurrentUser, DbSession
from api.schemas import ActionResult, PostingItemView, RunDetailView, RunProgressView
from factory.batch_worker import CancellationToken, retry_failed_items
from factory.models import Batch

router = APIRouter(prefix="/monitor/runs", tags=["monitor"])
KST = timezone(timedelta(hours=9))

_active_tokens: dict[int, CancellationToken] = {}

def register_cancel_token(batch_id: int, token: CancellationToken) -> None:
    _active_tokens[batch_id] = token

def unregister_cancel_token(batch_id: int) -> None:
    _active_tokens.pop(batch_id, None)

@router.get("", response_model=list[RunProgressView])
def list_runs(user: CurrentUser, db: DbSession):
    now = datetime.now(tz=KST)
    batches = db.scalars(select(Batch).join(Batch.campaign).where(
        Batch.campaign.has(user_id=user.id)).order_by(Batch.created_at.desc())).all()
    return [_progress(b, now) for b in batches]

@router.get("/{batch_id}", response_model=RunDetailView)
def get_run_detail(batch_id: int, user: CurrentUser, db: DbSession):
    batch = _get(batch_id, user.id, db)
    completed = failed = 0
    items = []
    for bi in batch.items:
        kw_vals = [kw.value for kw in bi.combination.keywords] if bi.combination else []
        kw_str = " ".join(kw_vals)
        if bi.status == "completed": completed += 1
        elif bi.status in ("failed", "cancelled"): failed += 1
        items.append(PostingItemView(
            title=kw_str, keywords=kw_str,
            status=_item_status(bi.status), url=bi.result_url,
            error=bi.error_message,
            completed_at=_fmt(bi.completed_at) if bi.completed_at else None))
    return RunDetailView(batch_id=batch.id, campaign_name=batch.campaign.name,
        account=batch.account.username, status=batch.status,
        completed=completed, failed=failed, total=len(batch.items), items=items)

@router.post("/{batch_id}/retry", response_model=ActionResult)
def retry_failed(batch_id: int, user: CurrentUser, db: DbSession):
    batch = _get(batch_id, user.id, db)
    count = retry_failed_items(batch); db.commit()
    if count == 0: return ActionResult(success=True, message="No failed items to retry.")
    return ActionResult(success=True, message=f"{count} items will be retried.")

@router.post("/{batch_id}/stop", response_model=ActionResult)
def stop_run(batch_id: int, user: CurrentUser, db: DbSession):
    batch = _get(batch_id, user.id, db)
    token = _active_tokens.get(batch_id)
    if token:
        token.cancel()
        return ActionResult(success=True, message="Stop signal sent. Running item will complete, then batch stops.")
    cancelled = 0
    for item in batch.items:
        if item.status == "pending": item.status = "cancelled"; cancelled += 1
    if cancelled > 0: batch.status = "stopped"; db.commit()
    return ActionResult(success=True, message=f"Batch stopped. {cancelled} items cancelled.")

def _get(batch_id, user_id, db):
    batch = db.get(Batch, batch_id)
    if batch is None or batch.campaign.user_id != user_id:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return batch

def _progress(b, now):
    total = len(b.items)
    completed = sum(1 for i in b.items if i.status == "completed")
    failed = sum(1 for i in b.items if i.status in ("failed", "cancelled"))
    pct = int(completed / total * 100) if total else 0
    return RunProgressView(batch_id=b.id, campaign_name=b.campaign.name,
        account=b.account.username, status=b.status,
        completed=completed, failed=failed, total=total, percentage=pct,
        started_at=_fmt(b.started_at), last_activity=_rel(b, now))

def _item_status(s):
    return {"completed":"Published","failed":"Failed","cancelled":"Cancelled","running":"Running","pending":"Waiting"}.get(s, s)

def _fmt(dt):
    if dt is None: return None
    if dt.tzinfo is None: dt = dt.replace(tzinfo=KST)
    return dt.strftime("%-m/%d %-I:%M %p")

def _rel(b, now):
    last = b.completed_at or b.started_at or b.created_at
    if last is None: return ""
    if last.tzinfo is None: last = last.replace(tzinfo=KST)
    m = int((now - last).total_seconds() / 60)
    if m < 1: return "just now"
    if m < 60: return f"{m} min ago"
    h = m // 60
    if h < 24: return f"{h} hours ago"
    return f"{(now-last).days} days ago"
