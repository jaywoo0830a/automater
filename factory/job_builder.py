"""
factory/job_builder.py
-----------------------
Translates DB models (Combination) into automator domain objects (PostingJob).

This module owns the mapping rules between the factory schema and the
automator builder API.  The rules are independently testable without
multiprocessing or a browser.

    Combination  ──→  TitleOption   (via _build_title_option)
                 ──→  Section[]     (via _build_body)
                 ──→  PostingJob    (via build_posting_job)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from automator.job import PostingJob
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

def build_posting_job(
    combo:        Any,
    account_opt:  AccountOption,
    scheduled_at: datetime,
) -> PostingJob:
    """
    Build a ready-to-run PostingJob from a DB Combination row.

    Args:
        combo:        factory.models.Combination instance.
        account_opt:  AccountOption for the batch's account.
        scheduled_at: Batch-level scheduled datetime (KST-aware).

    Returns:
        A fully configured PostingJob — call .run(editor) to execute.
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
    return (
        PostingJob
        .for_account(account_opt)
        .with_title(title_opt)
        .with_body(body)
        .with_publish(publish_opt)
        .with_setting(RunSetting())
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_values(combo: Any) -> dict[str, str]:
    """Build slug → value dict from combination's keywords."""
    has_suffix: bool = bool((combo.config or {}).get("has_suffix", 1))
    values: dict[str, str] = {}
    for kw in sorted(combo.keywords, key=lambda k: getattr(k.category, "id", 0)):
        slug        = kw.category.slug
        full_val    = kw.value
        display_val = kw.display_value
        values[slug] = full_val if (has_suffix or not display_val) else display_val
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
