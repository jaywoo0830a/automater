"""
tests/test_job_validation.py
-----------------------------
PostingJob.validate() — 잘못된 설정을 실행 전에 차단한다.

각 테스트는 규칙 하나가 위반됐을 때 ValueError 가 발생하는지 검증한다.
규칙이 충족됐을 때 validate() 가 통과하는 양성 케이스도 포함한다.
"""

import pytest
from dataclasses import replace
from datetime import datetime, timedelta

from automator.job import PostingJob
from automator.options import (
    AccountOption, TitleOption,
    FeaturedBlock, TextBlock,
    PublishOption, RunSetting, KST,
)


def _account():
    return AccountOption(username="id", password="pw", meta={"blog_id": "blog"})


def _base():
    return PostingJob.for_account(_account())


# ---------------------------------------------------------------------------
# AccountOption 필수 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_missing_account__raises_value_error():
    with pytest.raises(ValueError, match="AccountOption"):
        PostingJob().validate()


@pytest.mark.unit
def test_empty_username__raises_value_error():
    bad_acc = AccountOption(username="", password="pw", meta={})
    with pytest.raises(ValueError, match="username"):
        PostingJob.for_account(bad_acc).validate()


@pytest.mark.unit
def test_empty_password__raises_value_error():
    bad_acc = AccountOption(username="id", password="", meta={})
    with pytest.raises(ValueError, match="password"):
        PostingJob.for_account(bad_acc).validate()


@pytest.mark.unit
def test_whitespace_only_username__raises_value_error():
    bad_acc = AccountOption(username="   ", password="pw", meta={})
    with pytest.raises(ValueError, match="username"):
        PostingJob.for_account(bad_acc).validate()


# ---------------------------------------------------------------------------
# TitleOption 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_invalid_template_syntax__raises_value_error():
    with pytest.raises(ValueError):
        _base().with_title(TitleOption(template="{} bad", values={})).validate()


@pytest.mark.unit
def test_valid_template__passes_validation():
    _base().with_title(TitleOption(
        template="{region} {subject} {salt}",
        values={"region": "강남", "subject": "수학"},
    )).validate()


@pytest.mark.unit
def test_fixed_title__skips_template_validation():
    # fixed_title 이 있으면 template 검증 건너뜀
    _base().with_title(TitleOption(fixed_title="고정 제목", template="{bad}")).validate()


# ---------------------------------------------------------------------------
# Block 구성 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_two_featured_blocks__raises_value_error():
    with pytest.raises(ValueError, match="FeaturedBlock"):
        _base().with_body([FeaturedBlock("a.jpg"), FeaturedBlock("b.jpg")]).validate()


@pytest.mark.unit
def test_single_featured_block__passes_validation():
    _base().with_body([TextBlock(), FeaturedBlock("thumb.jpg")]).validate()


# ---------------------------------------------------------------------------
# PublishOption 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tag_min_exceeds_max__raises_value_error():
    with pytest.raises(ValueError, match="min_tags"):
        _base().with_publish(PublishOption(min_tags=20, max_tags=5)).validate()


@pytest.mark.unit
def test_backlink_ratio_over_100__raises_value_error():
    with pytest.raises(ValueError, match="backlink_ratio"):
        _base().with_publish(PublishOption(backlink_ratio=101)).validate()


@pytest.mark.unit
def test_fixed_schedule_without_at__raises_value_error():
    with pytest.raises(ValueError, match="at"):
        _base().with_publish(PublishOption(mode="fixed")).validate()


@pytest.mark.unit
def test_fixed_schedule_with_naive_datetime__raises_value_error():
    naive = datetime(2099, 1, 1, 9, 0)  # tzinfo=None
    with pytest.raises(ValueError, match="timezone-aware"):
        _base().with_publish(PublishOption(mode="fixed", at=naive)).validate()


@pytest.mark.unit
def test_fixed_schedule_with_past_datetime__raises_value_error():
    past = datetime(2000, 1, 1, 9, 0, tzinfo=KST)
    with pytest.raises(ValueError, match="미래"):
        _base().with_publish(PublishOption(mode="fixed", at=past)).validate()


@pytest.mark.unit
def test_random_window_with_zero_jitter__raises_value_error():
    future = datetime.now(tz=KST) + timedelta(hours=2)
    with pytest.raises(ValueError, match="jitter"):
        _base().with_publish(
            PublishOption(mode="random_window", at=future, jitter_minutes=0)
        ).validate()


@pytest.mark.unit
def test_immediate_mode__always_passes_validation():
    _base().with_publish(PublishOption(mode="immediate")).validate()


@pytest.mark.unit
def test_fixed_mode_with_future_aware_datetime__passes_validation():
    future = datetime.now(tz=KST) + timedelta(hours=2)
    _base().with_publish(PublishOption(mode="fixed", at=future)).validate()


# ---------------------------------------------------------------------------
# RunSetting 검증
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_negative_post_interval__raises_value_error():
    with pytest.raises(ValueError, match="post_interval"):
        _base().with_setting(RunSetting(post_interval=-1)).validate()


@pytest.mark.unit
def test_zero_max_daily_posts__raises_value_error():
    with pytest.raises(ValueError, match="max_daily_posts"):
        _base().with_setting(RunSetting(max_daily_posts=0)).validate()
