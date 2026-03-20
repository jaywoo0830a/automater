"""
factory/job_builder.py
-----------------------
Translates DB models (Combination) into a PostingSpec contract.

This module owns the mapping rules between the factory schema and the
automator contracts. No automator internals are imported — only the
shared contracts layer.

    Combination  -->  TitleOption   (via _build_title_option)
                 -->  Section[]     (via _build_body)
                 -->  PostingSpec   (via build_posting_spec)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    ParagraphBlock,
    PublishOption,
    RunSetting,
    Section,
    TitleOption,
)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_posting_spec(
    combo:        Any,
    account_opt:  AccountOption,
    scheduled_at: datetime,
) -> PostingSpec:
    """
    Build a PostingSpec from a DB Combination row.

    Args:
        combo:        factory.models.Combination instance.
        account_opt:  AccountOption for the batch's account.
        scheduled_at: Batch-level scheduled datetime (KST-aware).

    Returns:
        A fully configured PostingSpec ready for JobRunner.run().
    """
    title_opt   = _build_title_option(combo)
    body        = _build_body(combo)
    publish_opt = PublishOption(
        mode="fixed",
        at=(
            scheduled_at.replace(tzinfo=KST)
            if scheduled_at.tzinfo is None
            else scheduled_at
        ),
    )
    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        setting=RunSetting(),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_values(combo: Any) -> dict[str, str]:
    """Build slug → value dict from combination's keywords."""
    values: dict[str, str] = {}
    for kw in sorted(combo.keywords, key=lambda k: getattr(k.category, "id", 0)):
        values[kw.category.slug] = kw.value
    return values


def _build_title_option(combo: Any) -> TitleOption:
    """Build a TitleOption from a Combination's campaign template + keywords."""
    campaign = combo.campaign
    return TitleOption(
        template=campaign.title_template,
        values=_build_values(combo),
    )


def _build_body(combo: Any) -> list[Section]:
    """Build a Section list with ParagraphBlocks from combination keywords."""
    values: dict[str, str] = _build_values(combo)
    keyword = " ".join(values.values())
    prompt = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(ParagraphBlock(prompt=prompt) for _ in range(3)))]
