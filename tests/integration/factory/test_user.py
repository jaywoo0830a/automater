"""
tests/integration/factory/test_user.py
----------------------------
User model — ownership boundaries and auth fields.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.models import User, Account, Campaign, Platform


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------

def test_user_created_with_defaults(session: Session):
    user = User(email="a@b.com", password_hash="hash")
    session.add(user)
    session.flush()

    assert user.id is not None
    assert user.role == "operator"
    assert user.status == "active"
    assert user.display_name == ""
    assert user.last_login_at is None


def test_user_email_unique(session: Session):
    session.add(User(email="dup@b.com", password_hash="h1"))
    session.flush()
    session.add(User(email="dup@b.com", password_hash="h2"))
    with pytest.raises(Exception):
        session.flush()


# ---------------------------------------------------------------------------
# Ownership — Account.user_id
# ---------------------------------------------------------------------------

def test_account_belongs_to_user(session: Session):
    user = User(email="owner@test.com", password_hash="hash")
    session.add(user)
    session.flush()

    platform = session.scalars(select(Platform)).first()
    if not platform:
        platform = Platform(name="Test", slug="test_p", base_url="")
        session.add(platform)
        session.flush()

    acc = Account(
        user_id=user.id, platform_id=platform.id,
        username="blog_acc", password_enc="enc",
    )
    session.add(acc)
    session.flush()

    assert acc.owner.id == user.id
    assert acc in user.accounts


# ---------------------------------------------------------------------------
# Ownership — Campaign.user_id
# ---------------------------------------------------------------------------

def test_campaign_belongs_to_user(session: Session):
    user = User(email="camp@test.com", password_hash="hash")
    session.add(user)
    session.flush()

    platform = session.scalars(select(Platform)).first()
    if not platform:
        platform = Platform(name="Test", slug="test_p2", base_url="")
        session.add(platform)
        session.flush()

    camp = Campaign(
        user_id=user.id, platform_id=platform.id,
        name="My Campaign",
    )
    session.add(camp)
    session.flush()

    assert camp.owner.id == user.id
    assert camp in user.campaigns
