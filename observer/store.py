"""DB read/write operations for the observer daemon."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from automator.models.base import create_engine_from_url, create_session_factory
from automator.models.campaign import Campaign
from automator.models.observation import Observation
from automator.models.schedule import ObservationSchedule

logger = logging.getLogger(__name__)


class ObserverStore:
    """Thin wrapper around SQLAlchemy for observer-specific queries."""

    def __init__(self, mysql_url: str) -> None:
        self._engine = create_engine_from_url(mysql_url)
        self._Session = create_session_factory(self._engine)

    # ── reads ───────────────────────────────────────────────────────

    def fetch_due_schedules(self, now: datetime) -> list[ObservationSchedule]:
        """Return pending schedules whose scheduled_at <= *now*."""
        with self._Session() as session:
            schedules = (
                session.query(ObservationSchedule)
                .filter(
                    ObservationSchedule.scheduled_at <= now,
                    ObservationSchedule.status == "pending",
                )
                .order_by(ObservationSchedule.scheduled_at)
                .all()
            )
            session.expunge_all()
            return schedules

    # ── writes ──────────────────────────────────────────────────────

    def save_observation(
        self, obs: Observation, schedule_id: int,
    ) -> None:
        """Insert *obs* and mark the schedule as done."""
        with self._Session() as session:
            session.add(obs)
            session.flush()

            sched = session.get(ObservationSchedule, schedule_id)
            if sched:
                sched.status = "done"
                sched.observation_id = obs.id

            session.commit()
            logger.info(
                "Saved observation %d for schedule %d", obs.id, schedule_id,
            )

    def update_schedule_status(self, schedule_id: int, status: str) -> None:
        """Set *status* (e.g. ``skipped``) on a schedule row."""
        with self._Session() as session:
            sched = session.get(ObservationSchedule, schedule_id)
            if sched:
                sched.status = status
                session.commit()

    # ── auto-detect ────────────────────────────────────────────────

    def detect_new_campaigns(self) -> list[int]:
        """Find campaigns that have no schedules yet and generate them.

        Returns list of campaign IDs that got new schedules.
        """
        with self._Session() as session:
            sub = (
                select(ObservationSchedule.campaign_id)
                .group_by(ObservationSchedule.campaign_id)
            )
            new_campaigns = (
                session.query(Campaign)
                .filter(
                    Campaign.id.notin_(sub),
                    Campaign.published_at.isnot(None),
                )
                .all()
            )
            session.expunge_all()

        created_ids: list[int] = []
        for campaign in new_campaigns:
            try:
                self.generate_schedules(campaign.id)
                created_ids.append(campaign.id)
                logger.info(
                    "Auto-generated schedules for campaign %d (%s)",
                    campaign.id, campaign.keyword,
                )
            except Exception:
                logger.exception(
                    "Failed to generate schedules for campaign %d", campaign.id,
                )

        return created_ids

    # ── schedule generation ─────────────────────────────────────────

    def generate_schedules(self, campaign_id: int) -> list[ObservationSchedule]:
        """Generate time-based observation schedules from published_at.

        Schedule:
            1. 30 minutes after publish     (1 observation)
            2. D+1 through D+7, daily       (7 observations)
            3. D+14, D+21, D+28, D+35       (4 observations)
                                      Total: 12 observations
        """
        with self._Session() as session:
            campaign = session.get(Campaign, campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            if not campaign.published_at:
                raise ValueError(f"Campaign {campaign_id} has no published_at")

            pub = campaign.published_at
            times: list[datetime] = []

            # 1. 30 min after publish
            times.append(pub + timedelta(minutes=30))

            # 2. Daily for 7 days (same time of day as publish)
            for day in range(1, 8):
                times.append(pub + timedelta(days=day))

            # 3. Weekly for 4 weeks (D+14, D+21, D+28, D+35)
            for week in range(2, 6):
                times.append(pub + timedelta(weeks=week))

            created: list[ObservationSchedule] = []
            for t in times:
                sched = ObservationSchedule(
                    campaign_id=campaign_id,
                    scheduled_at=t,
                    status="pending",
                )
                session.add(sched)
                created.append(sched)

            session.commit()
            logger.info(
                "Generated %d schedules for campaign %d (published_at=%s)",
                len(created), campaign_id, pub,
            )
            session.expunge_all()
            return created

    # ── DDL ─────────────────────────────────────────────────────────

    def create_tables(self) -> None:
        """Create all model tables (initial setup / migrations)."""
        from automator.models.base import Base

        Base.metadata.create_all(self._engine)
        logger.info("Database tables created")

    # ── status ──────────────────────────────────────────────────────

    def print_status(self) -> None:
        """Print a summary of pending and upcoming schedules."""
        now = datetime.utcnow()
        with self._Session() as session:
            due = (
                session.query(ObservationSchedule)
                .filter(
                    ObservationSchedule.scheduled_at <= now,
                    ObservationSchedule.status == "pending",
                )
                .count()
            )
            upcoming = (
                session.query(ObservationSchedule)
                .filter(
                    ObservationSchedule.scheduled_at > now,
                    ObservationSchedule.status == "pending",
                )
                .count()
            )
            done = (
                session.query(ObservationSchedule)
                .filter(ObservationSchedule.status == "done")
                .count()
            )

        print(f"Now: {now.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Due (ready to run): {due}")
        print(f"  Upcoming: {upcoming}")
        print(f"  Done: {done}")
