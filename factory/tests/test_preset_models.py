"""
factory/tests/test_preset_models.py
--------------------------------------
PostLayout, LayoutSlot, PublishPreset, RunPreset model tests.

Verifies:
    - basic CRUD + defaults
    - Campaign nullable FK references (layout, publish_preset, run_preset)
    - LayoutSlot CASCADE delete when PostLayout is deleted
    - User ownership of presets
    - Campaign with all three presets
    - Campaign with no presets (backward compat)
"""

from __future__ import annotations

import pytest

from factory.models import (
    User, Platform, Campaign,
    PostLayout, LayoutSlot, PublishPreset, RunPreset,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(session) -> User:
    u = User(email="preset@test.com", password_hash="h", role="operator")
    session.add(u)
    session.flush()
    return u


def _platform(session) -> Platform:
    p = Platform(name="naver", slug="naver", base_url="https://blog.naver.com")
    session.add(p)
    session.flush()
    return p


def _campaign(session, user, platform, **kw) -> Campaign:
    c = Campaign(user_id=user.id, platform_id=platform.id, name="test", **kw)
    session.add(c)
    session.flush()
    return c


# ---------------------------------------------------------------------------
# PostLayout + LayoutSlot
# ---------------------------------------------------------------------------

class TestPostLayout:

    def test_create_layout_with_slots(self, session):
        user = _user(session)
        layout = PostLayout(user_id=user.id, name="edu-3-para", description="Education layout")
        session.add(layout)
        session.flush()

        slots = [
            LayoutSlot(layout_id=layout.id, sort_order=0, block_type="heading",
                       config={"level": 2, "text": "{keyword} guide"}),
            LayoutSlot(layout_id=layout.id, sort_order=1, block_type="paragraph",
                       config={"keyword": "{keyword}", "tone": "review"}),
            LayoutSlot(layout_id=layout.id, sort_order=2, block_type="paragraph",
                       config={"keyword": "{keyword}", "tone": "promotional"}),
        ]
        session.add_all(slots)
        session.flush()

        assert len(layout.slots) == 3
        assert layout.slots[0].block_type == "heading"
        assert layout.slots[0].config["level"] == 2

    def test_layout_owner_relationship(self, session):
        user = _user(session)
        layout = PostLayout(user_id=user.id, name="mine")
        session.add(layout)
        session.flush()

        assert layout.owner.email == "preset@test.com"
        assert layout in user.layouts

    def test_cascade_delete_slots(self, session):
        user = _user(session)
        layout = PostLayout(user_id=user.id, name="temp")
        session.add(layout)
        session.flush()

        session.add(LayoutSlot(layout_id=layout.id, sort_order=0, block_type="divider"))
        session.flush()

        assert session.query(LayoutSlot).count() == 1
        session.delete(layout)
        session.flush()
        assert session.query(LayoutSlot).count() == 0

    def test_slot_sort_order(self, session):
        user = _user(session)
        layout = PostLayout(user_id=user.id, name="ordered")
        session.add(layout)
        session.flush()

        session.add_all([
            LayoutSlot(layout_id=layout.id, sort_order=2, block_type="paragraph", config={"prompt": "last"}),
            LayoutSlot(layout_id=layout.id, sort_order=0, block_type="heading", config={"level": 1, "text": "first"}),
        ])
        session.flush()
        session.refresh(layout)

        assert layout.slots[0].sort_order == 0
        assert layout.slots[1].sort_order == 2


# ---------------------------------------------------------------------------
# PublishPreset
# ---------------------------------------------------------------------------

class TestPublishPreset:

    def test_create_with_config(self, session):
        user = _user(session)
        preset = PublishPreset(
            user_id=user.id,
            name="edu-publish",
            config={"mode": "random_window", "jitter_minutes": 45, "min_tags": 15},
        )
        session.add(preset)
        session.flush()

        assert preset.config["mode"] == "random_window"
        assert preset.config["jitter_minutes"] == 45

    def test_owner_relationship(self, session):
        user = _user(session)
        preset = PublishPreset(user_id=user.id, name="p", config={"mode": "fixed"})
        session.add(preset)
        session.flush()

        assert preset.owner.id == user.id
        assert preset in user.publish_presets


# ---------------------------------------------------------------------------
# RunPreset
# ---------------------------------------------------------------------------

class TestRunPreset:

    def test_create_with_config(self, session):
        user = _user(session)
        preset = RunPreset(
            user_id=user.id,
            name="safe-mode",
            config={"post_interval": 120, "headless": True, "max_daily_posts": 5},
        )
        session.add(preset)
        session.flush()

        assert preset.config["post_interval"] == 120

    def test_owner_relationship(self, session):
        user = _user(session)
        preset = RunPreset(user_id=user.id, name="r", config={"headless": False})
        session.add(preset)
        session.flush()

        assert preset in user.run_presets


# ---------------------------------------------------------------------------
# Campaign — nullable preset FKs
# ---------------------------------------------------------------------------

class TestCampaignPresets:

    def test_campaign_no_presets(self, session):
        """Backward compat: all three FKs null."""
        user = _user(session)
        platform = _platform(session)
        campaign = _campaign(session, user, platform)

        assert campaign.layout is None
        assert campaign.publish_preset is None
        assert campaign.run_preset is None

    def test_campaign_with_layout(self, session):
        user = _user(session)
        platform = _platform(session)
        layout = PostLayout(user_id=user.id, name="edu")
        session.add(layout)
        session.flush()

        campaign = _campaign(session, user, platform, layout_id=layout.id)
        assert campaign.layout.name == "edu"
        assert campaign in layout.campaigns

    def test_campaign_with_all_presets(self, session):
        user = _user(session)
        platform = _platform(session)

        layout = PostLayout(user_id=user.id, name="full")
        pub = PublishPreset(user_id=user.id, name="pub", config={"mode": "immediate"})
        run = RunPreset(user_id=user.id, name="run", config={"headless": True})
        session.add_all([layout, pub, run])
        session.flush()

        campaign = _campaign(
            session, user, platform,
            layout_id=layout.id,
            publish_preset_id=pub.id,
            run_preset_id=run.id,
        )

        assert campaign.layout.name == "full"
        assert campaign.publish_preset.config["mode"] == "immediate"
        assert campaign.run_preset.config["headless"] is True

    def test_multiple_campaigns_share_preset(self, session):
        user = _user(session)
        platform = _platform(session)
        pub = PublishPreset(user_id=user.id, name="shared", config={"mode": "fixed"})
        session.add(pub)
        session.flush()

        c1 = _campaign(session, user, platform, publish_preset_id=pub.id)
        c2 = Campaign(user_id=user.id, platform_id=platform.id, name="c2",
                       publish_preset_id=pub.id)
        session.add(c2)
        session.flush()

        assert len(pub.campaigns) == 2

    def test_detach_preset_sets_null(self, session):
        user = _user(session)
        platform = _platform(session)
        run = RunPreset(user_id=user.id, name="tmp", config={})
        session.add(run)
        session.flush()

        campaign = _campaign(session, user, platform, run_preset_id=run.id)
        assert campaign.run_preset is not None

        campaign.run_preset_id = None
        session.flush()
        session.refresh(campaign)
        assert campaign.run_preset is None
