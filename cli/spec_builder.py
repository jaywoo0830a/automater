"""
cli/spec_builder.py
--------------------
Combo + config dict → PostingSpec.

Parses the DSL post blocks, interpolates tokens, resolves image paths,
and assembles the automator contract objects.

Post block parsing rules (from 00_spec.yaml):
    string value → block's primary field
    dict value   → full config
    bare string  → valueless block (divider)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any

from automator.contracts import PostingSpec
from automator.options import (
    AccountOption,
    DividerBlock,
    FeaturedImageBlock,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    PublishOption,
    QuoteBlock,
    RunSetting,
    Section,
    TitleOption,
)
from automator.preset_loader import load_publish, load_setting

from cli.combo_builder import Combo
from cli.dsl import interpolate, interpolate_deep

_HEADING_RE = re.compile(r"^h([1-6])$")
_DEFAULT_PARAGRAPH_COUNT = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_spec(
    combo: Combo,
    config: dict[str, Any],
    account_index: int = 0,
) -> PostingSpec:
    """
    Build a PostingSpec from a Combo and campaign config dict.

    Account-level keys (headless, interval, etc.) override global run config.
    """
    account_dict = config["accounts"][account_index]
    account_opt = _build_account(account_dict)
    title_opt = _build_title(combo, config)
    body = _build_body(combo, config)
    publish_opt = _build_publish(config.get("publish", {}))

    run_config = merge_account_run(config.get("run", {}), account_dict)
    run_setting = _build_run(run_config)

    return PostingSpec(
        account=account_opt,
        title=title_opt,
        body=tuple(body),
        publish=publish_opt,
        setting=run_setting,
    )


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

def _build_account(acc: dict[str, Any]) -> AccountOption:
    """Map account dict to AccountOption."""
    return AccountOption(
        username=str(acc.get("username", "")),
        password=str(acc.get("password", "")),
        meta={k: v for k, v in acc.items()
              if k not in ("username", "password", "proxies", "session", "proxy")},
        proxies=[acc["proxy"]] if "proxy" in acc else list(acc.get("proxies", [])),
        session_path=str(acc.get("session", "")),
    )


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def _build_title(combo: Combo, config: dict[str, Any]) -> TitleOption:
    """Assemble TitleOption from combo + config pools."""
    pools_raw = config.get("pools", {})
    pools = {slug: tuple(values) for slug, values in pools_raw.items()}

    return TitleOption(
        template=combo.title_template,
        values=dict(combo.values),
        pools=pools,
    )


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------

def _build_body(combo: Combo, config: dict[str, Any]) -> list[Section]:
    """Parse post blocks or generate default body."""
    post = config.get("post", [])
    if not post:
        return _build_default_body(combo)

    values = combo.values
    pools = config.get("pools", {})
    images_dir = config.get("images", ".")
    blocks = []

    for entry in post:
        block = _parse_block(entry, values, pools, images_dir)
        if block is not None:
            blocks.append(block)

    return [Section(blocks=tuple(blocks))] if blocks else _build_default_body(combo)


def _build_default_body(combo: Combo) -> list[Section]:
    """Fallback: 3 ParagraphBlocks with combined keyword."""
    keyword = " ".join(combo.values.values())
    prompt = (
        f"{keyword}을(를) 홍보하는 블로그 글을 작성해주세요. "
        f"신뢰감 있는 톤으로 자연스럽게 서술해주세요."
    )
    return [Section(blocks=tuple(
        ParagraphBlock(prompt=prompt) for _ in range(_DEFAULT_PARAGRAPH_COUNT)
    ))]


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------

def _parse_block(
    entry: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
) -> Any:
    """Parse one post block entry into a Block dataclass."""
    # Bare string: "divider"
    if isinstance(entry, str):
        if entry == "divider":
            return DividerBlock()
        return None

    if not isinstance(entry, dict):
        return None

    # Single-key dict: {block_type: value}
    block_type, value = next(iter(entry.items()))

    # Heading: h1~h6
    heading_match = _HEADING_RE.match(block_type)
    if heading_match:
        level = int(heading_match.group(1))
        text = interpolate(str(value), values, pools)
        return HeadingBlock(level=level, text=text)

    # Paragraph
    if block_type == "paragraph":
        return _parse_paragraph(value, values, pools)

    # Image
    if block_type == "image":
        return _parse_image(value, values, pools, images_dir)

    # Thumbnail (featured image)
    if block_type == "thumbnail":
        return _parse_thumbnail(value, values, pools, images_dir)

    # Quote
    if block_type == "quote":
        return _parse_quote(value, values, pools)

    # List
    if block_type == "list":
        return _parse_list(value)

    # Divider
    if block_type == "divider":
        return DividerBlock()

    return None


def _parse_paragraph(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
) -> ParagraphBlock:
    """Parse paragraph block — value is the prompt string, DSL tokens interpolated."""
    prompt = interpolate(str(value), values, pools)
    return ParagraphBlock(prompt=prompt)


def _parse_image(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
) -> ImageBlock:
    """Parse image block — string or dict."""
    if isinstance(value, str):
        path = _resolve_path(images_dir, value)
        return ImageBlock(path=path)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools)
        src = cfg.get("src", cfg.get("path", ""))
        path = _resolve_path(images_dir, src)
        return ImageBlock(
            path=path,
            alt=str(cfg.get("alt", "")),
        )

    return ImageBlock()


def _parse_thumbnail(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
    images_dir: str,
) -> FeaturedImageBlock:
    """Parse thumbnail block — string or dict."""
    if isinstance(value, str):
        path = _resolve_path(images_dir, value)
        return FeaturedImageBlock(path=path)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools)
        src = cfg.get("src", cfg.get("path", ""))
        path = _resolve_path(images_dir, src)
        return FeaturedImageBlock(
            path=path,
            overlay_text=str(cfg.get("overlay", cfg.get("overlay_text", ""))),
        )

    return FeaturedImageBlock()


def _parse_quote(
    value: Any,
    values: dict[str, str],
    pools: dict[str, list[str]],
) -> QuoteBlock:
    """Parse quote block — string or dict."""
    if isinstance(value, str):
        text = interpolate(value, values, pools)
        return QuoteBlock(text=text)

    if isinstance(value, dict):
        cfg = interpolate_deep(dict(value), values, pools)
        return QuoteBlock(
            text=str(cfg.get("text", "")),
            attribution=str(cfg.get("by", cfg.get("attribution", ""))),
        )

    return QuoteBlock()


def _parse_list(value: Any) -> ListBlock:
    """Parse list block — list of strings."""
    if isinstance(value, list):
        items = tuple(str(item) for item in value)
        return ListBlock(items=items)
    return ListBlock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_path(images_dir: str, filename: str) -> str:
    """Join images_dir + filename, normalizing ./ prefix."""
    if not filename:
        return ""
    if not images_dir or images_dir == ".":
        return filename
    return str(PurePosixPath(images_dir) / filename)


def _build_publish(publish_config: dict[str, Any]) -> PublishOption:
    """Build PublishOption from config dict with schedule parsing."""
    if not publish_config:
        return PublishOption(mode="immediate")

    schedule = parse_schedule(publish_config.get("schedule"))

    return PublishOption(
        mode=schedule["mode"],
        at=schedule.get("at"),
        jitter_minutes=schedule.get("jitter_minutes", 30),
        tags=list(publish_config.get("tags", [])),
        visibility=publish_config.get("visibility", "public"),
    )


# ---------------------------------------------------------------------------
# Schedule parsing
# ---------------------------------------------------------------------------

_RANDOM_RE = re.compile(r"random\s*[±+\-]\s*(\d+)\s*min", re.IGNORECASE)
_FIXED_RE = re.compile(r"fixed\s+(\d{1,2}):(\d{2})", re.IGNORECASE)

_KST = timezone(timedelta(hours=9))


def parse_schedule(raw: Any) -> dict[str, Any]:
    """
    Parse a schedule string into mode, at, jitter_minutes.

    Formats:
        immediate      → mode="immediate"
        fixed HH:MM    → mode="fixed", at=today HH:MM KST
        random ±Nmin   → mode="random_window", jitter_minutes=N, at=now KST
        None / ""      → mode="immediate"
    """
    if not raw:
        return {"mode": "immediate", "at": None}

    s = str(raw).strip().lower()

    if s == "immediate" or not s:
        return {"mode": "immediate", "at": None}

    fixed_match = _FIXED_RE.match(s)
    if fixed_match:
        hour, minute = int(fixed_match.group(1)), int(fixed_match.group(2))
        now = datetime.now(tz=_KST)
        at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if at <= now:
            at += timedelta(days=1)
        return {"mode": "fixed", "at": at, "jitter_minutes": 0}

    random_match = _RANDOM_RE.match(s)
    if random_match:
        jitter = int(random_match.group(1))
        now = datetime.now(tz=_KST)
        return {"mode": "random_window", "at": now, "jitter_minutes": jitter}

    return {"mode": "immediate", "at": None}


# ---------------------------------------------------------------------------
# Account override
# ---------------------------------------------------------------------------

_ACCOUNT_IDENTITY_KEYS = {
    "username", "password", "blog_id", "session", "proxy",
    "proxies", "meta", "platform", "api_url", "api_key",
}


def merge_account_run(
    global_run: dict[str, Any],
    account: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge account-level overrides into global run config.

    Account keys that are identity fields (username, password, etc.)
    are excluded. Everything else overrides the global value.
    """
    merged = dict(global_run)
    for key, value in account.items():
        if key not in _ACCOUNT_IDENTITY_KEYS:
            merged[key] = value
    return merged


def _build_run(run_config: dict[str, Any]) -> RunSetting:
    """Build RunSetting from config dict."""
    if not run_config:
        return RunSetting()

    interval = _parse_duration(run_config.get("interval", "60s"))
    upload_delay = _parse_duration(run_config.get("upload_delay", "1500ms"))

    return RunSetting(
        post_interval=interval,
        max_daily_posts=int(run_config.get("max_daily", 10)),
        on_failure=run_config.get("on_failure", "stop"),
        headless=bool(run_config.get("headless", True)),
        upload_delay_ms=upload_delay,
    )


def _parse_duration(value: Any) -> int:
    """Parse duration string: 60s → 60, 5min → 300, 1500ms → 1500."""
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    if s.endswith("ms"):
        return int(s[:-2])
    if s.endswith("min"):
        return int(s[:-3]) * 60
    if s.endswith("s"):
        return int(s[:-1])
    try:
        return int(s)
    except ValueError:
        return 60
