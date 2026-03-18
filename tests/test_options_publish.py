"""
PublishOption 스케줄 검증 테스트.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from dataclasses import replace
from unittest.mock import MagicMock

from automator.editor import BlogEditor
from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption, PublishOption, KST,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return (PostingJob.for_account(_account())
            .with_title(TitleOption(fixed_title="T")))


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fixed_mode_requires_at():
    with pytest.raises(ValueError, match="at"):
        _base().with_publish(PublishOption(mode="fixed")).validate()


@pytest.mark.unit
def test_fixed_mode_requires_aware_datetime():
    naive = datetime(2099, 1, 1, 9, 0)  # tzinfo=None
    with pytest.raises(ValueError, match="timezone-aware"):
        _base().with_publish(PublishOption(mode="fixed", at=naive)).validate()


@pytest.mark.unit
def test_fixed_mode_requires_future():
    past = datetime(2000, 1, 1, 9, 0, tzinfo=KST)
    with pytest.raises(ValueError, match="미래"):
        _base().with_publish(PublishOption(mode="fixed", at=past)).validate()


@pytest.mark.unit
def test_random_window_requires_positive_jitter():
    future = datetime.now(tz=KST) + timedelta(hours=2)
    with pytest.raises(ValueError, match="jitter"):
        _base().with_publish(PublishOption(
            mode="random_window", at=future, jitter_minutes=0
        )).validate()


@pytest.mark.unit
def test_immediate_mode_always_valid():
    _base().with_publish(PublishOption(mode="immediate")).validate()


# ---------------------------------------------------------------------------
# _resolve_schedule
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_immediate_resolves_to_none():
    editor  = MagicMock(spec=BlogEditor)
    _base().with_publish(PublishOption(mode="immediate")).run(editor)
    publish_args = editor.publish.call_args[1].get("schedule_at") or \
                   editor.publish.call_args[0][0] if editor.publish.call_args[0] else None
    assert editor.publish.called
    call_kw = editor.publish.call_args
    schedule_at = call_kw.kwargs.get("schedule_at") if call_kw.kwargs else call_kw[1].get("schedule_at")
    assert schedule_at is None


@pytest.mark.unit
def test_fixed_resolves_to_exact_time():
    future = datetime.now(tz=KST) + timedelta(hours=2)
    editor = MagicMock(spec=BlogEditor)
    _base().with_publish(PublishOption(mode="fixed", at=future)).run(editor)
    call_kw = editor.publish.call_args
    schedule_at = (call_kw.kwargs.get("schedule_at")
                   if call_kw.kwargs
                   else call_kw[1].get("schedule_at"))
    assert schedule_at == future


@pytest.mark.unit
def test_random_window_within_bounds():
    future  = datetime.now(tz=KST) + timedelta(hours=3)
    jitter  = 30
    results = set()
    for _ in range(30):
        pub = PostingJob._resolve_schedule(
            PublishOption(mode="random_window", at=future, jitter_minutes=jitter)
        )
        delta = abs((pub - future).total_seconds())
        assert delta <= jitter * 60 + 1
        results.add(round(delta, 1))
    assert len(results) > 1   # 무작위성 확인
