"""
api/routes/batches.py — listBatches, dispatchBatches, getBatch, startBatch,
                         cancelBatch, retryBatchItem
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import joinedload

from api.deps import Db, CurrentUser
from api.schemas import BatchOut, DispatchRequest, DispatchResult
from factory.models import Campaign, Batch, BatchItem
from factory.dispatcher import BatchDispatcher

router = APIRouter(tags=["batches"])


def _own_campaign(db, user, campaign_id) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


def _own_batch(db, user, batch_id) -> Batch:
    b = db.query(Batch).options(joinedload(Batch.items)).filter(Batch.id == batch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    c = db.get(Campaign, b.campaign_id)
    if not c or c.user_id != user.id:
        raise HTTPException(status_code=404, detail="Batch not found")
    return b


@router.get("/campaigns/{id}/batches")
def list_batches(
    id: int, db: Db, user: CurrentUser,
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    _own_campaign(db, user, id)
    q = db.query(Batch).filter(Batch.campaign_id == id)
    if status:
        q = q.filter(Batch.status == status)
    total = q.count()
    items = q.order_by(Batch.scheduled_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "page": page, "per_page": per_page,
        "total": total, "total_pages": (total + per_page - 1) // per_page,
        "items": [BatchOut.model_validate(b) for b in items],
    }


@router.post("/campaigns/{id}/batches/dispatch", response_model=DispatchResult)
def dispatch_batches(id: int, body: DispatchRequest, db: Db, user: CurrentUser):
    _own_campaign(db, user, id)
    dispatcher = BatchDispatcher(db, body.schedule_base)
    result = dispatcher.dispatch()
    db.commit()
    return DispatchResult(
        batches_created=result.batches_created,
        accounts_used=result.accounts_used,
        combos_assigned=result.combos_assigned,
    )


@router.get("/batches/{id}", response_model=BatchOut)
def get_batch(id: int, db: Db, user: CurrentUser):
    return _own_batch(db, user, id)


@router.post("/batches/{id}/start")
def start_batch(id: int, db: Db, user: CurrentUser):
    b = _own_batch(db, user, id)
    if b.status != "pending":
        raise HTTPException(status_code=400, detail=f"Batch status is '{b.status}', expected 'pending'")
    b.status = "running"
    db.commit()
    return {"worker_pid": None}


@router.post("/batches/{id}/cancel")
def cancel_batch(id: int, db: Db, user: CurrentUser):
    b = _own_batch(db, user, id)
    if b.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel batch with status '{b.status}'")
    b.status = "cancelled"
    db.commit()
    return {"status": "cancelled"}


@router.post("/batch-items/{id}/retry")
def retry_batch_item(id: int, db: Db, user: CurrentUser):
    item = db.get(BatchItem, id)
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found")
    _own_batch(db, user, item.batch_id)
    if item.status != "failed":
        raise HTTPException(status_code=400, detail=f"Item status is '{item.status}', expected 'failed'")
    item.status = "pending"
    item.error_message = None
    item.completed_at = None
    db.commit()
    return {"status": "pending"}
