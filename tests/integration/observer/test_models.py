"""Integration tests for automator.models — schema + basic persistence."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import inspect

from automator.models.base import Base, create_engine_from_url
from automator.models.campaign import Campaign
from automator.models.observation import Observation
from automator.models.schedule import ObservationSchedule


# ── campaign ────────────────────────────────────────────────────────

def test_campaign_roundtrip(db_session):
    c = Campaign(
        blog_id="myblog",
        keyword="test",
        platform="naver",
        published_at=datetime.utcnow(),
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    assert c.id is not None
    assert c.created_at is not None


def test_campaign_allows_null_published_at(db_session):
    c = Campaign(blog_id="myblog", keyword="x", platform="naver")
    db_session.add(c)
    db_session.commit()
    assert c.published_at is None


# ── observation ─────────────────────────────────────────────────────

def test_observation_roundtrip(db_session):
    c = Campaign(blog_id="a", keyword="b", platform="naver")
    db_session.add(c)
    db_session.flush()

    obs = Observation(
        campaign_id=c.id,
        rank=1,
        found_in="unified",
        session_ip="1.2.3.4",
        fingerprint="hash",
        user_agent="UA",
        viewport_width=1920,
        viewport_height=1080,
    )
    db_session.add(obs)
    db_session.commit()
    assert obs.id is not None


def test_observation_nullable_metrics(db_session):
    c = Campaign(blog_id="a", keyword="b")
    db_session.add(c)
    db_session.flush()

    obs = Observation(
        campaign_id=c.id,
        session_ip="0.0.0.0",
        fingerprint="h",
        user_agent="u",
        viewport_width=1,
        viewport_height=1,
    )
    db_session.add(obs)
    db_session.commit()

    assert obs.rank is None
    assert obs.found_in is None
    assert obs.scroll_pct is None
    assert obs.dwell_seconds is None


# ── schedule ────────────────────────────────────────────────────────

def test_schedule_belongs_to_campaign(db_session):
    c = Campaign(blog_id="a", keyword="b")
    db_session.add(c)
    db_session.flush()

    sched = ObservationSchedule(
        campaign_id=c.id,
        scheduled_at=datetime.utcnow() + timedelta(days=1),
        status="pending",
    )
    db_session.add(sched)
    db_session.commit()

    db_session.refresh(sched)
    assert sched.campaign.id == c.id


def test_schedule_default_status_is_pending(db_session):
    c = Campaign(blog_id="a", keyword="b")
    db_session.add(c)
    db_session.flush()

    sched = ObservationSchedule(
        campaign_id=c.id, scheduled_at=datetime.utcnow(),
    )
    db_session.add(sched)
    db_session.commit()
    assert sched.status == "pending"


# ── schema ──────────────────────────────────────────────────────────

def test_all_tables_created(db_engine):
    tables = set(inspect(db_engine).get_table_names())
    assert {"campaigns", "observations", "observation_schedules"} <= tables


# ── engine helpers ──────────────────────────────────────────────────

def test_engine_adds_charset_to_mysql_url():
    engine = create_engine_from_url("mysql+pymysql://user:pass@host/db")
    try:
        assert "charset=utf8mb4" in str(engine.url)
    finally:
        engine.dispose()


def test_engine_does_not_add_charset_twice():
    engine = create_engine_from_url(
        "mysql+pymysql://user:pass@host/db?charset=utf8",
    )
    try:
        assert str(engine.url).count("charset") == 1
    finally:
        engine.dispose()


def test_engine_leaves_sqlite_url_untouched():
    engine = create_engine_from_url("sqlite:///:memory:")
    try:
        assert "charset" not in str(engine.url)
    finally:
        engine.dispose()
