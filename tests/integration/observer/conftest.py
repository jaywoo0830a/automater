"""Shared fixtures for observer integration tests.

All fixtures are function-scoped — each test gets a fresh in-memory
SQLite database so tests can't bleed state into each other.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from automator.models.base import (
    Base,
    create_engine_from_url,
    create_session_factory,
)
from observer.store import ObserverStore


@pytest.fixture
def db_engine():
    """Fresh in-memory SQLite engine with schema created."""
    engine = create_engine_from_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    """ORM session bound to the in-memory engine."""
    Session_ = create_session_factory(db_engine)
    with Session_() as session:
        yield session


@pytest.fixture
def store():
    """Fresh ObserverStore with an in-memory SQLite database."""
    s = ObserverStore("sqlite:///:memory:")
    s.create_tables()
    yield s
    s._engine.dispose()
