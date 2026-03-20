"""
tests/integration/test_publish_option.py
-------------------------------------------
PublishOption schedule resolution through ContentBuilder.

Replaces: tests/test_publish_option.py
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from automator.contracts import PostingSpec
from automator.content_builder import ContentBuilder
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.options import (
    AccountOption, TitleOption, PublishOption, KST,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "b"})


def _spec(**kw):
    kw.setdefault("account", _account())
    kw.setdefault("title", TitleOption(fixed_title="T"))
    return PostingSpec(**kw)


@pytest.fixture
def builder():
    return ContentBuilder(StubTextGenerator(), NoopImageProcessor())


def test_immediate_schedule_returns_none(builder):
    post = builder.build(_spec(publish=PublishOption(mode="immediate")))
    assert post.schedule_at is None


def test_fixed_schedule_returns_exact_time(builder):
    future = datetime.now(tz=KST) + timedelta(hours=2)
    post = builder.build(_spec(publish=PublishOption(mode="fixed", at=future)))
    assert post.schedule_at == future


def test_random_window_within_jitter(builder):
    base = datetime.now(tz=KST) + timedelta(hours=2)
    pub = PublishOption(mode="random_window", at=base, jitter_minutes=30)
    post = builder.build(_spec(publish=pub))
    delta = abs((post.schedule_at - base).total_seconds())
    assert delta <= 30 * 60
