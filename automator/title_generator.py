"""
automator/title_generator.py
-----------------------------
Title generation functions.

    generate_title(option)         -> str
    validate_template(template)    -> None (raises ValueError)

No class — option in, title out.
"""

from __future__ import annotations

import random
import re

from automator.options import TitleOption

_TOKEN_RE = re.compile(r"\{(\w*)\}")


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------

def validate_template(template: str) -> None:
    """
    Raise ValueError if template is invalid.

    Rules:
      - Not empty / whitespace-only.
      - At least one {slug} token.
      - All tokens are valid Python identifiers.
      - No empty braces {}.
      - No duplicate tokens.
    """
    if not template or not template.strip():
        raise ValueError("template must not be empty")

    raw_tokens = _TOKEN_RE.findall(template)

    if not raw_tokens:
        raise ValueError(
            "template contains no {slug} tokens — "
            "use e.g. \"{region} {subject} {salt_suffix}\""
        )

    for tok in raw_tokens:
        if not tok:
            raise ValueError(
                "template contains empty braces {} — "
                "every token must have a slug name"
            )
        if not tok.isidentifier():
            raise ValueError(
                f"token {{{tok!r}}} is not a valid identifier — "
                "use lowercase letters, digits, and underscores only"
            )

    duplicates = {t for t in raw_tokens if raw_tokens.count(t) > 1}
    if duplicates:
        raise ValueError(f"template contains duplicate token(s): {duplicates}")


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

def generate_title(
    option: TitleOption,
    rng: random.Random | None = None,
) -> str:
    """
    Generate a post title from a TitleOption.

    fixed_title -> return as-is.
    Otherwise substitute {slug} tokens:
      - tokens in values  -> deterministic substitution
      - tokens in pools   -> random choice from pool

    Raises ValueError if values and pools share any key (namespace collision).

    Args:
        option: TitleOption with template, values, and optional pools.
        rng:    Optional random.Random for deterministic tests.

    Returns:
        The generated title string.
    """
    if option.fixed_title:
        return option.fixed_title

    if not option.template or not option.template.strip():
        if option.pools:
            raise ValueError(
                "template must not be empty when pools are provided. "
                "Use fixed_title for a literal title, or provide a template."
            )
        return ""

    validate_template(option.template)

    collisions = set(option.values.keys()) & set(option.pools.keys())
    if collisions:
        raise ValueError(
            f"namespace collision: {collisions} found in both values and pools"
        )

    rng = rng or random.Random(option.seed)
    tokens = _TOKEN_RE.findall(option.template)
    sub = dict(option.values)

    for token in tokens:
        if token in option.pools:
            pool = option.pools[token]
            sub[token] = rng.choice(pool) if pool else ""

    return option.template.format(**sub)
