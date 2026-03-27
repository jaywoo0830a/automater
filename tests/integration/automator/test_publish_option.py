"""
tests/integration/test_publish_option.py
-------------------------------------------
Schedule resolution through ContentBuilder.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from automator.contracts import PostingSpec
from automator.content_builder import ContentBuilder
from automator.stubs import StubTextGenerator, NoopImageProcessor
from automator.options import AccountOption, KST


def _account():
    return AccountOption(username="id", password="pw")


def _spec(**kw):
    kw.setdefault("account", _account())
    kw.setdefault("title", "T")
    return PostingSpec(**kw)


@pytest.fixture
def builder():
    return ContentBuilder(StubTextGenerator(), NoopImageProcessor())


def test_immediate_schedule_returns_none(builder):
    post = builder.build(_spec())
    assert post.schedule_at is None


def test_scheduled_returns_exact_time(builder):
    future = datetime.now(tz=KST) + timedelta(hours=2)
    post = builder.build(_spec(schedule_at=future))
    assert post.schedule_at == future
