"""
cli/spec_builder.py
--------------------
Translate KeywordCombo + CampaignConfig into a PostingSpec.

Reuses automator's contract layer directly:
    - create_block()   for layout → Block conversion
    - load_publish()   for PublishOption deserialization
    - load_setting()   for RunSetting deserialization

No DB access, no ORM — all data comes from CampaignConfig.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any

from automator.block_factory import create_block
from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    ParagraphBlock,
    PublishOption,
    Section,
    TitleOption,
)
from automator.preset_loader import load_publish, load_setting

from cli.campaign_config import (
    AccountEntry,
    CampaignConfig,
    LayoutSlotEntry,
    TitleConfig,
)
from cli.combo_builder import KeywordCombo

KST = timezone(timedelta(hours=9))

_DEFAULT_PARAGRAPH_COUNT = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_spec(
    combo: KeywordCombo,
    config: CampaignConfig,
    account_entry: AccountEntry,
    schedule_at: datetime | None = None,
) -> PostingSpec:
    """
    Build a PostingSpec from a keyword combination and campaign config.

    Args:
        combo:         One keyword combination from combo_builder.
        config:        Full campaign configuration.
        account_entry: The account to post with.
        schedule_at:   Optional scheduled time. Defaults to now (KST).
    """
    account_opt = build_account_option(account_entry)
    title_opt = _build_title_option(combo, config)
    body = _build_body(combo, config)

    scheduled = schedule_at or datetime.now(tz=KST)
    publish_opt = _build_publish(config.publish_config, scheduled)
    run_setting = load_setting(config.run_config or None)

    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        setting=run_setting,
    )


def build_account_option(entry: AccountEntry) -> AccountOption:
    """Convert an AccountEntry dataclass to an automator AccountOption."""
    return AccountOption(
        username=entry.username,
        password=entry.password,
        meta=dict(entry.meta),
        proxies=list(entry.proxies),
        session_path=entry.session_path,
    )


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _build_title_option(
    combo: KeywordCombo,
    config: CampaignConfig,
) -> TitleOption:
    """Assemble a TitleOption from tokens, combo values, and palettes."""
    template = _build_template(config.title, combo.spacing_pattern)
    pools = _build_pools(config)

    return TitleOption(
        template=template,
        values=dict(combo.values),
        pools=pools,
    )


def _build_template(
    title_config: TitleConfig,
    spacing_pattern: dict[str, int],
) -> str:
    """
    Build the title template string from token sequence + spacing.

    keyword/pool tokens → {slug} placeholder.
    literal tokens      → raw value text.
    Spacing pattern controls whether a space separates each pair.
    """
    tokens = title_config.tokens
    if not tokens:
        return ""

    parts: list[str] = []
    for token in tokens:
        if token.type == "literal":
            parts.append(token.value or "")
        else:
            parts.append(f"{{{token.slug}}}")

    if not spacing_pattern:
        return " ".join(parts)

    # Apply spacing pattern between consecutive tokens
    result = parts[0]
    for i in range(1, len(parts)):
        prev_slug = tokens[i - 1].slug
        has_space = spacing_pattern.get(prev_slug, 1)
        separator = " " if has_space else ""
        result += separator + parts[i]
    return result


def _build_pools(config: CampaignConfig) -> dict[str, tuple[str, ...]]:
    """Build slug → pool tuple from palettes config."""
    pool_slugs = {t.slug for t in config.title.tokens if t.type == "pool"}
    return {
        slug: tuple(values)
        for slug, values in config.palettes.items()
        if slug in pool_slugs
    }


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------

def _build_body(
    combo: KeywordCombo,
    config: CampaignConfig,
) -> list[Section]:
    """Build body sections from layout slots or fallback default."""
    if not config.layout:
        return _build_default_body(combo)

    keyword = " ".join(combo.values.values())
    media_resolver = _make_media_resolver(config)

    blocks = []
    for slot in config.layout:
        resolved_config = _resolve_media_in_config(
            slot.config, slot.block_type, media_resolver,
        )
        block = create_block(
            block_type=slot.block_type,
            config=resolved_config,
            values=combo.values,
            keyword=keyword,
            media_resolver=None,  # Already resolved above
        )
        blocks.append(block)

    return [Section(blocks=tuple(blocks))] if blocks else _build_default_body(combo)


def _build_default_body(combo: KeywordCombo) -> list[Section]:
    """Fallback: 3 ParagraphBlocks with combined keyword prompt."""
    keyword = " ".join(combo.values.values())
    prompt = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(ParagraphBlock(prompt=prompt) for _ in range(_DEFAULT_PARAGRAPH_COUNT)))]


# ---------------------------------------------------------------------------
# Media resolution
# ---------------------------------------------------------------------------

def _make_media_resolver(config: CampaignConfig) -> dict[str, str]:
    """Build media_id → absolute path lookup from MediaMap."""
    base = config.media.base_dir
    return {
        media_id: str(PurePosixPath(base) / filename)
        for media_id, filename in config.media.files.items()
    }


def _resolve_media_in_config(
    config: dict[str, Any],
    block_type: str,
    resolver: dict[str, str],
) -> dict[str, Any]:
    """
    If config has media_id and no explicit path, resolve to file path.

    Mutates nothing — returns a new dict.
    """
    media_id = config.get("media_id")
    if media_id is None:
        return dict(config)

    media_key = str(media_id)
    if block_type in {"image", "featured"} and "path" not in config:
        resolved_path = resolver.get(media_key, "")
        result = {**config, "path": resolved_path}
        result.pop("media_id", None)
        return result

    result = dict(config)
    result.pop("media_id", None)
    return result


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def _build_publish(
    publish_config: dict[str, Any],
    scheduled_at: datetime,
) -> PublishOption:
    """Build PublishOption from config dict + scheduled time."""
    if not publish_config:
        return PublishOption(mode="immediate")

    merged = dict(publish_config)
    mode = merged.get("mode", "immediate")

    if mode != "immediate":
        merged["at"] = scheduled_at
        return load_publish(merged, scheduled_at)

    return load_publish(merged, scheduled_at)
