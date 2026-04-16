"""automator.models -- Shared SQLAlchemy 2.0 models."""

from automator.models.base import Base, create_engine_from_url, create_session_factory
from automator.models.campaign import Campaign
from automator.models.schedule import ObservationSchedule
from automator.models.observation import Observation

__all__ = [
    "Base",
    "create_engine_from_url",
    "create_session_factory",
    "Campaign",
    "ObservationSchedule",
    "Observation",
]
