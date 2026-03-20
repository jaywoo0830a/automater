"""
automator/title_generator.py
-----------------------------
TitleGenerator: TitleOption → title string.

Template format
---------------
Python str.format() style {slug} tokens.

    "{region} {subject} {learning_type} {salt}"  → "강남 수학 과외 강력 추천"
    "{salt} {region} {subject} {learning_type}"  → "검증된 강남 수학 과외"

{salt} is a special token — the pool is determined by its position:
    first token  → prefix_salts
    last token   → suffix_salts
    middle token → all_salts (prefix ∪ suffix)

Salt data comes from TitleOption.prefix_salts / suffix_salts,
which are typically loaded from CampaignPalette before construction.

Usage:
    gen = TitleGenerator(TitleOption(
        template = "{region} {subject} {learning_type} {salt}",
        values   = {"region": "강남", "subject": "수학", "learning_type": "과외"},
        suffix_salts = ("강력 추천", "즉시 가능"),
    ))
    title = gen.generate()  # e.g. "강남 수학 과외 강력 추천"
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from automator.options import TitleOption

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

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
            "use e.g. \"{region} {subject} {salt}\""
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
# TitleGenerator
# ---------------------------------------------------------------------------

class TitleGenerator:
    """
    Generates a blog post title from a TitleOption.

    Salt data is read directly from TitleOption.prefix_salts / suffix_salts.
    No file I/O — the caller is responsible for loading palette data from DB.

    Args:
        option: TitleOption with template, values, and optional salt tuples.
        rng:    Optional random.Random for deterministic tests.
    """

    def __init__(
        self,
        option: TitleOption,
        rng: random.Random | None = None,
    ) -> None:
        self._opt = option
        self._rng = rng or random.Random(option.seed)

        if not option.fixed_title:
            if not option.template or not option.template.strip():
                # Salt data supplied but no template → user error
                if option.prefix_salts or option.suffix_salts:
                    raise ValueError(
                        "template must not be empty when salts are provided. "
                        "Use fixed_title for a literal title, or provide a template."
                    )
                self._prefix_salts: list[str] = []
                self._suffix_salts: list[str] = []
                self._all_salts:    list[str] = []
            else:
                validate_template(option.template)
                self._prefix_salts = list(option.prefix_salts)
                self._suffix_salts = list(option.suffix_salts)
                self._all_salts    = list(dict.fromkeys(
                    list(option.prefix_salts) + list(option.suffix_salts)
                ))

    def generate(self) -> str:
        """
        Return the post title.

        fixed_title → return as-is.
        Otherwise substitute {slug} tokens from values dict,
        pick a random salt for {salt}.
        """
        if self._opt.fixed_title:
            return self._opt.fixed_title

        if not self._opt.template:
            return ""

        tokens = _TOKEN_RE.findall(self._opt.template)
        sub    = dict(self._opt.values)

        if "salt" in tokens:
            pool = self._pick_salt_pool(tokens)
            if pool:
                sub["salt"] = self._rng.choice(pool)
            else:
                sub["salt"] = ""

        return self._opt.template.format(**sub)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pick_salt_pool(self, tokens: list[str]) -> list[str]:
        """
        Select salt pool based on {salt} position in token list.

            index 0      → prefix_salts
            last index   → suffix_salts
            middle index → all_salts
        """
        idx      = tokens.index("salt")
        last_idx = len(tokens) - 1
        if idx == 0:
            return self._prefix_salts
        if idx == last_idx:
            return self._suffix_salts
        return self._all_salts
