"""
tests/integration/test_spec_validator.py
-------------------------------------------
SpecValidator.validate() — rejects invalid specs before execution.

Replaces: tests/test_job_validation.py
"""

import pytest
from datetime import datetime, timedelta

from automator.contracts import PostingSpec
from automator.spec_validator import SpecValidator
from automator.options import (
    AccountOption, TitleOption,
    FeaturedImageBlock, ParagraphBlock, Section,
    PublishOption, RunSetting, KST,
)


def _account(**kw):
    defaults = {"username": "id", "password": "pw"}
    defaults.update(kw)
    return AccountOption(**defaults)


def _spec(**kw):
    kw.setdefault("account", _account())
    return PostingSpec(**kw)


@pytest.fixture
def v():
    return SpecValidator()


# ---------------------------------------------------------------------------
# Account validation
# ---------------------------------------------------------------------------

def test_empty_username_rejected(v):
    with pytest.raises(ValueError, match="username"):
        v.validate(_spec(account=_account(username="  ")))


def test_empty_password_rejected(v):
    with pytest.raises(ValueError, match="password"):
        v.validate(_spec(account=_account(password="")))


# ---------------------------------------------------------------------------
# Title validation
# ---------------------------------------------------------------------------

def test_bad_template_rejected(v):
    with pytest.raises(ValueError, match="token"):
        v.validate(_spec(title=TitleOption(template="{}")))


def test_valid_template_passes(v):
    v.validate(_spec(title=TitleOption(template="{keyword:region} {keyword:subject}")))


# ---------------------------------------------------------------------------
# Section layout
# ---------------------------------------------------------------------------

def test_two_featured_images_rejected(v):
    body = (Section(blocks=(FeaturedImageBlock(), FeaturedImageBlock())),)
    with pytest.raises(ValueError, match="FeaturedImageBlock"):
        v.validate(_spec(body=body))


# ---------------------------------------------------------------------------
# Publish validation
# ---------------------------------------------------------------------------

def test_fixed_schedule_without_at_rejected(v):
    with pytest.raises(ValueError, match="at"):
        v.validate(_spec(publish=PublishOption(mode="scheduled")))


def test_fixed_schedule_naive_datetime_rejected(v):
    with pytest.raises(ValueError, match="timezone"):
        v.validate(_spec(publish=PublishOption(
            mode="scheduled",
            at=datetime(2099, 1, 1, 9, 0),
        )))


def test_valid_fixed_schedule_passes(v):
    future = datetime.now(tz=KST) + timedelta(hours=2)
    v.validate(_spec(publish=PublishOption(mode="scheduled", at=future)))


def test_tags_min_greater_than_max_rejected(v):
    with pytest.raises(ValueError, match="min_tags"):
        v.validate(_spec(publish=PublishOption(min_tags=25, max_tags=10)))


# ---------------------------------------------------------------------------
# RunSetting validation
# ---------------------------------------------------------------------------

def test_negative_post_interval_rejected(v):
    with pytest.raises(ValueError, match="post_interval"):
        v.validate(_spec(setting=RunSetting(post_interval=-1)))


def test_zero_max_daily_posts_rejected(v):
    with pytest.raises(ValueError, match="max_daily_posts"):
        v.validate(_spec(setting=RunSetting(max_daily_posts=0)))


def test_valid_spec_passes(v):
    """A fully valid spec does not raise."""
    v.validate(_spec(
        title="T",
        body=(Section(blocks=(ParagraphBlock(),)),),
    ))
