"""
automator/title_generator.py
-----------------------------
Title generation with a simple DSL.

DSL format
----------
    {keyword:slug}  — substituted from TitleOption.values[slug]
    {pool:slug}     — random choice from TitleOption.pools[slug]
    plain text      — kept as-is (spacing is what you type)

Examples::

    "{pool:salt_prefix} {keyword:region} {keyword:subject} 과외 {pool:salt_suffix}"
    → "검증된 강남 수학 과외 강력 추천"

    "{pool:salt_prefix} {keyword:region}{keyword:subject}과외 {pool:salt_suffix}"
    → "전문 강남수학과외 즉시 가능"

Public API
----------
    generate_title(option)         -> str
    validate_template(template)    -> None (raises ValueError)
"""

from __future__ import annotations

import random
import re

from automator.options import TitleOption

_TOKEN_RE = re.compile(r"\{([^}]*)\}")
_VALID_TYPES = {"keyword", "pool"}


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------

def validate_template(template: str) -> None:
    """
    Raise ValueError if template syntax is invalid.

    Rules:
      - Not empty / whitespace-only.
      - At least one {type:slug} token.
      - Every token has format {keyword:slug} or {pool:slug}.
      - No duplicate type:slug pairs.
    """
    if not template or not template.strip():
        raise ValueError("template must not be empty")

    raw_tokens = _TOKEN_RE.findall(template)

    if not raw_tokens:
        raise ValueError(
            "template contains no {type:slug} tokens — "
            "use e.g. \"{keyword:region} {pool:salt_suffix}\""
        )

    parsed: list[tuple[str, str]] = []
    for raw in raw_tokens:
        pair = _parse_token(raw)
        parsed.append(pair)

    seen: set[tuple[str, str]] = set()
    for pair in parsed:
        if pair in seen:
            raise ValueError(
                f"template contains duplicate token: "
                f"{{{pair[0]}:{pair[1]}}}"
            )
        seen.add(pair)


def _parse_token(raw: str) -> tuple[str, str]:
    """
    Parse a raw token string into (type, slug).

    Raises ValueError if the format is invalid.
    """
    if ":" not in raw or not raw.strip():
        raise ValueError(
            f"invalid token {{{raw}}} — "
            f"use {{keyword:slug}} or {{pool:slug}}"
        )

    parts = raw.split(":", 1)
    token_type = parts[0].strip()
    slug = parts[1].strip()

    if not token_type or not slug:
        raise ValueError(
            f"invalid token {{{raw}}} — "
            f"both type and slug are required"
        )

    if token_type not in _VALID_TYPES:
        raise ValueError(
            f"invalid token type '{token_type}' in {{{raw}}} — "
            f"must be one of: {sorted(_VALID_TYPES)}"
        )

    return (token_type, slug)


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

def generate_title(
    option: TitleOption,
    rng: random.Random | None = None,
) -> str:
    """
    Generate a post title from a TitleOption.

    Substitutes {keyword:slug} and {pool:slug} tokens in the template.

    Args:
        option: TitleOption with template, values, and optional pools.
        rng:    Optional random.Random for deterministic tests.

    Returns:
        The generated title string.

    Raises:
        ValueError: Template syntax invalid.
        KeyError:   Referenced slug not found in values or pools.
    """
    if not option.template or not option.template.strip():
        if option.pools:
            raise ValueError(
                "template must not be empty when pools are provided. "
                "Pass a plain str as PostingSpec.title for a literal title."
            )
        return ""

    validate_template(option.template)

    rng = rng or random.Random(option.seed)

    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        token_type, slug = _parse_token(raw)

        if token_type == "keyword":
            if slug not in option.values:
                raise KeyError(
                    f"keyword slug '{slug}' not found in values. "
                    f"Available: {sorted(option.values.keys())}"
                )
            return option.values[slug]

        # pool
        if slug not in option.pools:
            raise KeyError(
                f"pool slug '{slug}' not found in pools. "
                f"Available: {sorted(option.pools.keys())}"
            )
        pool = option.pools[slug]
        return rng.choice(pool) if pool else ""

    return _TOKEN_RE.sub(_replace, option.template)
