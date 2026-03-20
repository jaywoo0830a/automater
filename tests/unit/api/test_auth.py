"""
tests/unit/api/test_auth.py
------------------------------
Auth route unit tests — register, login, getMe, updateMe, changePassword.

Uses FastAPI TestClient with dependency overrides.
No real DB, no real JWT — everything is faked.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_db, get_current_user


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _user(id=1, email="test@test.com", role="operator", status="active"):
    return SimpleNamespace(
        id=id,
        email=email,
        password_hash="$2b$12$fakehash",
        display_name="Tester",
        role=role,
        status=status,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        last_login_at=None,
    )


def _mock_db(users=None):
    """Return a mock session that simulates SQLAlchemy add/commit/refresh."""
    db = MagicMock()
    user_list = users or []
    _counter = {"id": 100}

    def fake_query(model):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = user_list[0] if user_list else None
        return q

    def fake_refresh(obj):
        """Simulate DB defaults that SQLAlchemy would set after commit."""
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = _counter["id"]
            _counter["id"] += 1
        if hasattr(obj, "role") and obj.role is None:
            obj.role = "operator"
        if hasattr(obj, "status") and obj.status is None:
            obj.status = "active"
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

    db.query = fake_query
    db.get = lambda model, id: next((u for u in user_list if u.id == id), None)
    db.refresh = fake_refresh
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app = create_app()
    db = _mock_db()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authed_client():
    app = create_app()
    user = _user()
    db = _mock_db([user])
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c, user, db
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegister:

    def test_register_returns_201(self, client):
        resp = client.post("/auth/register", json={
            "email": "new@test.com",
            "password": "12345678",
        })
        assert resp.status_code == 201

    def test_register_missing_password_returns_422(self, client):
        resp = client.post("/auth/register", json={"email": "a@b.com"})
        assert resp.status_code == 422

    def test_register_short_password_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "email": "a@b.com", "password": "short",
        })
        assert resp.status_code == 422


class TestLogin:

    def test_login_missing_fields_returns_422(self, client):
        resp = client.post("/auth/login", json={"email": "a@b.com"})
        assert resp.status_code == 422


class TestGetMe:

    def test_me_without_token_returns_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_with_token_returns_user(self, authed_client):
        client, user, _ = authed_client
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email


class TestUpdateMe:

    def test_update_display_name(self, authed_client):
        client, user, db = authed_client
        resp = client.patch("/auth/me", json={"display_name": "New Name"})
        assert resp.status_code == 200


class TestChangePassword:

    def test_change_password_missing_fields_returns_422(self, authed_client):
        client, _, _ = authed_client
        resp = client.put("/auth/password", json={"current_password": "old"})
        assert resp.status_code == 422
