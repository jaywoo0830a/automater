"""
tests/integration/test_spec_builder.py
-----------------------------------------
PostingSpec construction — immutability and field assignment.

Replaces: tests/test_job_builder.py (PostingJob builder pattern).
PostingSpec is a frozen dataclass — no builder chain, just construction.
"""

import pytest
from dataclasses import FrozenInstanceError

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    ParagraphBlock, ImageBlock, FeaturedImageBlock, Section,
    PublishOption,
)


def _account():
    return AccountOption(username="id", password="pw")


def test_spec_requires_account():
    """PostingSpec needs an account."""
    spec = PostingSpec(account=_account())
    assert spec.account.username == "id"


def test_spec_defaults():
    """Omitted fields get sensible defaults."""
    spec = PostingSpec(account=_account())
    assert spec.body == ()
    assert spec.schedule_at is None


def test_spec_is_frozen():
    """PostingSpec is immutable."""
    spec = PostingSpec(account=_account())
    with pytest.raises(FrozenInstanceError):
        spec.account = _account()  # type: ignore[misc]


def test_spec_with_full_body():
    """PostingSpec accepts a body tuple of Sections."""
    body = (
        Section(blocks=(ParagraphBlock(prompt="intro"),)),
        Section(blocks=(ImageBlock(path="/tmp/a.jpg"),)),
    )
    spec = PostingSpec(account=_account(), body=body)
    assert len(spec.body) == 2
    assert isinstance(spec.body[0].blocks[0], ParagraphBlock)


def test_two_specs_independent():
    """Two specs from same data are independent objects."""
    a = PostingSpec(account=_account(), title="A")
    b = PostingSpec(account=_account(), title="B")
    assert a.title != b.title
