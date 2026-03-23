"""api/step4.py — Step 4: Run preview and execute."""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from api.deps import CurrentUser, DbSession
from api.schemas import (AccountAssignment, FriendlyError, RunConfig, RunPreviewView, RunStartResult)
from automator.title_generator import generate_title
from automator.options import TitleOption
from factory.combo_generator import ComboGenerator
from factory.dispatcher import BatchDispatcher
from factory.job_builder import _build_template, _build_values, _build_pools
from factory.models import Account, Batch, Campaign, Combination, PostLayout

router = APIRouter(prefix="/step4/run", tags=["step-4-run"])
KST = timezone(timedelta(hours=9))

@router.post("/preview", response_model=RunPreviewView)
def preview_run(body: RunConfig, user: CurrentUser, db: DbSession):
    campaign, layout = _load(body, db)
    unused = db.scalar(select(func.count(Combination.id)).where(
        Combination.campaign_id == campaign.id, Combination.used_at.is_(None))) or 0
    accounts = _available(user.id, db)
    assigns = _assign(accounts, unused)
    sched_summary = est_finish = None
    if body.publish_mode == "scheduled" and body.schedule_start:
        sched_summary = f"Starting {body.schedule_start.strftime('%-m/%d %-I:%M %p')}, every {body.schedule_interval_minutes} min"
        est_finish = (body.schedule_start + timedelta(minutes=unused * body.schedule_interval_minutes)).strftime("%-m/%d %-I:%M %p")
    titles = _sample_titles(campaign, db)
    return RunPreviewView(campaign_name=campaign.name, template_name=layout.name if layout else "(default)",
        total_combinations=unused, accounts=assigns, publish_mode=body.publish_mode,
        schedule_summary=sched_summary, estimated_finish=est_finish, sample_titles=titles,
        warnings=[] if accounts else ["No accounts available."])

@router.post("/execute", response_model=RunStartResult, status_code=201)
def execute_run(body: RunConfig, user: CurrentUser, db: DbSession):
    campaign, layout = _load(body, db)
    unused = db.scalar(select(func.count(Combination.id)).where(
        Combination.campaign_id == campaign.id, Combination.used_at.is_(None))) or 0
    if unused == 0:
        gen = ComboGenerator(session=db, campaign_id=campaign.id); gen.run(); db.flush()
        unused = db.scalar(select(func.count(Combination.id)).where(
            Combination.campaign_id == campaign.id, Combination.used_at.is_(None))) or 0
    if unused == 0:
        raise HTTPException(status_code=422, detail=FriendlyError(message="No combinations.", suggestion="Add keywords in Step 2.").model_dump())
    if layout and campaign.layout_id != layout.id: campaign.layout_id = layout.id; db.flush()
    base = body.schedule_start or datetime.now(tz=KST)
    result = BatchDispatcher(session=db, schedule_base=base).dispatch(); db.commit()
    batch_ids = [b.id for b in db.scalars(select(Batch).where(Batch.campaign_id == campaign.id, Batch.status == "pending")).all()]
    return RunStartResult(success=True, message=f"{result.combos_assigned} posts scheduled across {result.accounts_used} accounts.",
                          batch_ids=batch_ids, total_posts=result.combos_assigned)

def _load(body, db):
    c = db.get(Campaign, body.campaign_id)
    if c is None: raise HTTPException(status_code=422, detail=FriendlyError(message="Campaign not found.").model_dump())
    return c, db.get(PostLayout, body.template_id)

def _available(uid, db):
    now = datetime.now(tz=KST)
    out = []
    for a in db.scalars(select(Account).where(Account.user_id == uid, Account.status == "active")).all():
        if a.last_used_at is None: out.append(a); continue
        last = a.last_used_at.replace(tzinfo=KST) if a.last_used_at.tzinfo is None else a.last_used_at
        if now >= last + timedelta(days=a.cooldown_days): out.append(a)
    return out

def _assign(accounts, total):
    if not accounts: return []
    per = total // len(accounts); rem = total % len(accounts)
    return [AccountAssignment(username=a.username, posts_assigned=per + (1 if i < rem else 0)) for i, a in enumerate(accounts)]

def _sample_titles(campaign, db, count=5):
    combos = db.scalars(select(Combination).where(Combination.campaign_id == campaign.id, Combination.used_at.is_(None)).limit(count)).all()
    rng = random.Random(42); titles = []
    for co in combos:
        try:
            titles.append(generate_title(TitleOption(template=_build_template(campaign), values=_build_values(co), pools=_build_pools(campaign), seed=42), rng=rng))
        except (ValueError, KeyError): pass
    return titles
