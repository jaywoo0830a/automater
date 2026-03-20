"""
api/routes/batches.py — listBatches, dispatchBatches, getBatch, startBatch,
                         cancelBatch, retryBatchItem
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from api.deps import Db, CurrentUser
from api.schemas import BatchOut, DispatchRequest, DispatchResult
from factory.models import Campaign, Batch, BatchItem
from factory.dispatcher import BatchDispatcher

router = APIRouter(tags=["batches"])

MEDIA_DIR = Path(os.getenv("MEDIA_STORAGE_DIR", "uploads"))


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
def start_batch(
    id: int,
    db: Db,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    """
    Start executing a batch.

    Validates the batch is pending, then schedules background execution.
    Returns immediately with the worker PID. Poll GET /batches/{id}
    for status updates.
    """
    b = _own_batch(db, user, id)
    if b.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Batch status is '{b.status}', expected 'pending'",
        )

    batch_id = b.id
    background_tasks.add_task(_run_batch_background, batch_id)

    return {"worker_pid": os.getpid(), "status": "starting"}


def _run_batch_background(batch_id: int) -> None:
    """
    Background task — runs in its own DB session after the HTTP response.

    Imports are deferred to avoid circular dependencies and to keep
    Playwright out of the module-level scope.
    """
    from sqlalchemy.orm import joinedload as jl
    from factory.db import get_engine
    from factory.models import Batch as BatchModel
    from factory.batch_worker import BatchWorker
    from factory.storage import LocalStorage
    from factory.media_resolver import build_media_resolver
    from automator.spec_validator import SpecValidator
    from automator.content_builder import ContentBuilder
    from automator.runner import JobRunner
    from automator.gemini_generator import GeminiGenerator
    from automator.local_processor import LocalImageProcessor

    engine = get_engine()
    storage = LocalStorage(base_dir=MEDIA_DIR)

    with Session(engine) as session:
        batch = session.query(BatchModel).options(
            jl(BatchModel.items),
            jl(BatchModel.account),
            jl(BatchModel.campaign),
        ).filter(BatchModel.id == batch_id).first()

        if not batch or batch.status not in ("pending", "running"):
            return

        text_gen = GeminiGenerator()
        img_proc = LocalImageProcessor()
        runner = JobRunner(SpecValidator(), ContentBuilder(text_gen, img_proc))
        resolver = build_media_resolver(session, storage)
        editor_factory = _create_playwright_editor_factory(batch.account)

        worker = BatchWorker(
            runner=runner,
            editor_factory=editor_factory,
            media_resolver=resolver,
        )
        worker.run_batch(batch)
        session.commit()


def _create_playwright_editor_factory(account):
    """
    Build an EditorFactory that creates SmartEditorOne with Playwright.

    Launches one browser for the batch, reuses it for all items.
    Browser is closed when the factory goes out of scope.
    """
    from playwright.sync_api import sync_playwright
    from automator.smart_editor import SmartEditorOne

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    session_path = f"{account.username}_session.json"

    blog_id = (account.extra or {}).get("blog_id", "")
    write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

    import os
    if os.path.exists(session_path):
        ctx = browser.new_context(
            storage_state=session_path,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
    else:
        ctx = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")

    def factory(acc):
        page = ctx.new_page()
        return SmartEditorOne(page, write_url, dry_run=False)

    return factory


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
