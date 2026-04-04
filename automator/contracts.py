"""
automator/contracts.py
-----------------------
PostingSpec — shared contract between factory and automator.

This is a pure data class with no execution logic. It sits in Zone A
(contracts layer) so that both packages depend on it without depending
on each other.

factory builds PostingSpec → runner executes PostingSpec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from automator.options import (
    AccountOption,
    Alignment,
    TitleOption,
    Section,
    PublishOption,
)


@dataclass(frozen=True)
class PostingSpec:
    """
    Immutable posting specification — all data needed to produce one post.

    factory creates this from a Combination row.
    automator.runner.JobRunner executes it against a BlogEditor.

    schedule_at: None = immediate publish, datetime = scheduled publish.
    align:       Text alignment for the entire post (left/center/right).
                 None = use editor default (left).
    """
    account:     AccountOption
    title:       TitleOption | str      = ""
    body:        tuple[Section, ...]    = ()
    publish:     PublishOption          = field(default_factory=PublishOption)
    schedule_at: datetime | None       = None
    align:       Alignment | None      = None
