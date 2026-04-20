"""Integration tests: full observer pipeline from campaign insert to due schedule.

Simulates the real-world timeline:
  T+0    campaign inserted (published_at recorded)
  T+0    observer daemon tick → detect_new_campaigns → 12 schedules generated
  T+30m  first schedule becomes due (fetch_due_schedules returns it)
  T+1d   daily schedules become due one by one
  T+2w   weekly schedules become due

These tests drive the clock via an explicit ``now`` argument to
fetch_due_schedules, so they run instantly without sleep.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from automator.models.campaign import Campaign as DBCampaign
from automator.models.observation import Observation
from automator.models.schedule import ObservationSchedule


def _insert_campaign(store, published_at: datetime) -> int:
    """Simulate API Worker inserting a campaign row."""
    with store._Session() as session:
        c = DBCampaign(
            blog_id="myblog",
            keyword="test keyword",
            platform="naver",
            published_at=published_at,
        )
        session.add(c)
        session.commit()
        return c.id


# ── Stage 1: schedule generation on first tick ─────────────────────

def test_first_tick_generates_12_schedules(store):
    """T+0: campaign inserted, observer's first tick creates schedules."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    cid = _insert_campaign(store, pub)

    # Before tick: 0 schedules
    now = pub
    assert store.fetch_due_schedules(now) == []

    # First tick calls detect_new_campaigns
    created = store.detect_new_campaigns()
    assert cid in created

    # 12 schedule rows now exist for this campaign
    with store._Session() as session:
        schedules = session.query(ObservationSchedule).filter(
            ObservationSchedule.campaign_id == cid,
        ).all()
    assert len(schedules) == 12


# ── Stage 2: 30-minute mark ────────────────────────────────────────

def test_nothing_due_before_30min_mark(store):
    """T+29m: no schedule should be due yet."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_29m = pub + timedelta(minutes=29)
    due = store.fetch_due_schedules(at_29m)
    assert due == []


def test_first_schedule_due_exactly_at_30min(store):
    """T+30m: exactly one schedule (the 30-min observation) should be due."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_30m = pub + timedelta(minutes=30)
    due = store.fetch_due_schedules(at_30m)
    assert len(due) == 1
    assert due[0].scheduled_at == pub + timedelta(minutes=30)
    assert due[0].status == "pending"


def test_still_one_due_at_31min(store):
    """T+31m: still just the 30-min schedule."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_31m = pub + timedelta(minutes=31)
    due = store.fetch_due_schedules(at_31m)
    assert len(due) == 1


# ── Stage 3: after first observation recorded ──────────────────────

def test_completed_schedule_no_longer_due(store):
    """After worker records observation, that schedule isn't returned again."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    cid = _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_30m = pub + timedelta(minutes=30)
    [first_due] = store.fetch_due_schedules(at_30m)

    # Simulate worker saving observation
    obs = Observation(
        campaign_id=cid,
        rank=5,
        found_in="unified",
        session_ip="1.2.3.4",
        fingerprint="fp",
        user_agent="UA",
        viewport_width=1920,
        viewport_height=1080,
    )
    store.save_observation(obs, first_due.id)

    # Next tick at same time: no due (it's been marked done)
    due_after = store.fetch_due_schedules(at_30m)
    assert due_after == []


# ── Stage 4: D+1 daily rollover ────────────────────────────────────

def test_day_plus_1_becomes_due(store):
    """T+24h: D+1 schedule also becomes due (30min one is still pending too)."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_1d = pub + timedelta(days=1)
    due = store.fetch_due_schedules(at_1d)

    # Both the 30-min and the D+1 schedule are now in the past
    times = sorted(s.scheduled_at for s in due)
    assert pub + timedelta(minutes=30) in times
    assert pub + timedelta(days=1) in times


# ── Stage 5: weekly schedule ───────────────────────────────────────

def test_week_2_schedule_appears_at_day_14(store):
    """T+14d: D+14 weekly schedule becomes due (plus all prior)."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_14d = pub + timedelta(weeks=2)
    due = store.fetch_due_schedules(at_14d)
    times = {s.scheduled_at for s in due}

    # D+14 must be present
    assert pub + timedelta(weeks=2) in times


def test_all_12_schedules_due_after_35_days(store):
    """T+35d: every schedule is in the past."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_end = pub + timedelta(weeks=5, days=1)
    due = store.fetch_due_schedules(at_end)
    assert len(due) == 12


# ── Stage 6: ordering invariant ────────────────────────────────────

def test_fetch_due_is_ordered_by_scheduled_at(store):
    """Worker processes oldest-first — rely on this ordering."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)
    store.detect_new_campaigns()

    at_end = pub + timedelta(weeks=5, days=1)
    due = store.fetch_due_schedules(at_end)
    times = [s.scheduled_at for s in due]
    assert times == sorted(times)


# ── Stage 7: isolation between campaigns ───────────────────────────

def test_two_campaigns_get_independent_schedules(store):
    """Two campaigns published at different times each get their own 12 rows."""
    pub_a = datetime(2026, 4, 17, 14, 0, 0)
    pub_b = datetime(2026, 4, 17, 15, 30, 0)

    cid_a = _insert_campaign(store, pub_a)
    cid_b = _insert_campaign(store, pub_b)
    store.detect_new_campaigns()

    with store._Session() as session:
        a = session.query(ObservationSchedule).filter_by(campaign_id=cid_a).count()
        b = session.query(ObservationSchedule).filter_by(campaign_id=cid_b).count()
    assert a == 12
    assert b == 12


def test_detect_new_campaigns_is_idempotent(store):
    """Calling detect_new_campaigns twice should NOT duplicate schedules."""
    pub = datetime(2026, 4, 17, 14, 0, 0)
    _insert_campaign(store, pub)

    first = store.detect_new_campaigns()
    second = store.detect_new_campaigns()

    assert len(first) == 1
    assert second == []  # nothing new on second call
