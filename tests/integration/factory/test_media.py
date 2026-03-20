"""
tests/integration/factory/test_media.py
------------------------------
Media model tests.

Verifies:
    - basic CRUD + defaults
    - User ownership
    - content_type and size_bytes stored correctly
    - unique storage_path constraint
"""

from __future__ import annotations

import pytest

from factory.models import User, Media


def _user(session) -> User:
    u = User(email="media@test.com", password_hash="h", role="operator")
    session.add(u)
    session.flush()
    return u


class TestMedia:

    def test_create_media(self, session):
        user = _user(session)
        m = Media(
            user_id=user.id,
            original_name="academy.jpg",
            content_type="image/jpeg",
            storage_path=f"{user.id}/abc123.jpg",
            size_bytes=45_000,
        )
        session.add(m)
        session.flush()

        assert m.id is not None
        assert m.original_name == "academy.jpg"
        assert m.content_type == "image/jpeg"
        assert m.size_bytes == 45_000

    def test_defaults(self, session):
        user = _user(session)
        m = Media(
            user_id=user.id,
            original_name="photo.png",
            content_type="image/png",
            storage_path=f"{user.id}/def456.png",
            size_bytes=12_000,
        )
        session.add(m)
        session.flush()

        assert m.created_at is not None

    def test_owner_relationship(self, session):
        user = _user(session)
        m = Media(
            user_id=user.id,
            original_name="thumb.jpg",
            content_type="image/jpeg",
            storage_path=f"{user.id}/ghi789.jpg",
            size_bytes=8_000,
        )
        session.add(m)
        session.flush()

        assert m.owner.email == "media@test.com"
        assert m in user.media

    def test_unique_storage_path(self, session):
        user = _user(session)
        path = f"{user.id}/unique.jpg"
        session.add(Media(
            user_id=user.id, original_name="a.jpg",
            content_type="image/jpeg", storage_path=path, size_bytes=1,
        ))
        session.flush()

        session.add(Media(
            user_id=user.id, original_name="b.jpg",
            content_type="image/jpeg", storage_path=path, size_bytes=2,
        ))
        with pytest.raises(Exception):
            session.flush()

    def test_multiple_media_per_user(self, session):
        user = _user(session)
        for i in range(3):
            session.add(Media(
                user_id=user.id,
                original_name=f"img{i}.jpg",
                content_type="image/jpeg",
                storage_path=f"{user.id}/file{i}.jpg",
                size_bytes=1000 * (i + 1),
            ))
        session.flush()

        assert len(user.media) == 3
