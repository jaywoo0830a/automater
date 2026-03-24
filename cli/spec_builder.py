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

    Args:
        combo:         One keyword×title combination.
        config:        Full campaign config (from load_config).
        account_index: Which account to use (default first).
    """
    account_opt = _build_account(config["accounts"][account_index])
    title_opt = _build_title(combo, config)
    body = _build_body(combo, config)
    publish_opt = _build_publish(config.get("publish", {}))
    run_setting = _build_run(config.get("run", {}))

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
    """Build PublishOption — immediate mode for CLI."""
    if not publish_config:
        return PublishOption(mode="immediate")
    return PublishOption(
        mode="immediate",
        tags=list(publish_config.get("tags", [])),
        visibility=publish_config.get("visibility", "public"),
    )


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
