"""
factory/job_builder.py
-----------------------
Translates DB models (Combination) into a PostingSpec contract.

Dynamic composition:
    campaign.layout          -> body (LayoutSlot[] -> Block[])
    campaign.publish_preset  -> PublishOption (JSON config)
    campaign.run_preset      -> RunSetting (JSON config)
    All three nullable — null means use system defaults.

    media_resolver           -> resolves media_id in slot config to file path
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from automator.contracts import PostingSpec
from automator.block_factory import create_block
from automator.preset_loader import load_publish, load_setting
from automator.options import (
    AccountOption,
    ParagraphBlock,
    Section,
    TitleOption,
)

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_posting_spec(
    combo:          Any,
    account_opt:    AccountOption,
    scheduled_at:   datetime,
    media_resolver: Callable[[int], str] | None = None,
) -> PostingSpec:
    """
    Build a PostingSpec from a DB Combination row.

    Args:
        combo:          Combination ORM instance.
        account_opt:    AccountOption for the batch's account.
        scheduled_at:   Batch-level scheduled datetime (KST-aware).
        media_resolver: Resolves media_id -> absolute file path.
                        Required when layout slots use media_id.
    """
    campaign = combo.campaign
    scheduled_kst = (
        scheduled_at.replace(tzinfo=KST)
        if scheduled_at.tzinfo is None
        else scheduled_at
    )

    title_opt = _build_title(combo)

    layout = getattr(campaign, "layout", None)
    body = (
        _build_body_from_layout(layout, combo, media_resolver)
        if layout is not None
        else _build_body_default(combo)
    )

    pub_preset = getattr(campaign, "publish_preset", None)
    publish_config = pub_preset.config if pub_preset else None
    publish_opt = load_publish(publish_config, scheduled_kst)

    run_preset = getattr(campaign, "run_preset", None)
    run_config = run_preset.config if run_preset else None
    setting = load_setting(run_config)

    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        setting=setting,
    )


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _build_values(combo: Any) -> dict[str, str]:
    """Build slug -> value dict from combination's keywords."""
    values: dict[str, str] = {}
    for kw in sorted(combo.keywords, key=lambda k: getattr(k.category, "id", 0)):
        values[kw.category.slug] = kw.value
    return values


def _build_title(combo: Any) -> TitleOption:
    """Build a TitleOption from campaign template + combination keywords."""
    campaign = combo.campaign
    return TitleOption(
        template=campaign.title_template,
        values=_build_values(combo),
    )


# ---------------------------------------------------------------------------
# Body — from PostLayout or fallback
# ---------------------------------------------------------------------------

def _build_body_from_layout(
    layout: Any,
    combo: Any,
    media_resolver: Callable[[int], str] | None = None,
) -> list[Section]:
    """
    Convert PostLayout.slots into a Section with Block dataclasses.

    Each LayoutSlot's config JSON may contain {keyword}, {region}, etc.
    for text interpolation, and media_id for image resolution.
    """
    values = _build_values(combo)
    keyword = " ".join(values.values())

    blocks = []
    for slot in sorted(layout.slots, key=lambda s: s.sort_order):
        block = create_block(
            block_type=slot.block_type,
            config=dict(slot.config) if slot.config else {},
            values=values,
            keyword=keyword,
            media_resolver=media_resolver,
        )
        blocks.append(block)

    return [Section(blocks=tuple(blocks))] if blocks else _build_body_default(combo)


def _build_body_default(combo: Any) -> list[Section]:
    """Fallback: 3 ParagraphBlocks with combined keyword prompt."""
    values = _build_values(combo)
    keyword = " ".join(values.values())
    prompt = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(ParagraphBlock(prompt=prompt) for _ in range(3)))]
