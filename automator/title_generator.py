"""
automator/title_generator.py
-----------------------------
TitleGenerator: TitleOption → 제목 문자열

Template 형식
-------------
Python str.format() 스타일 {slug} 토큰.

    "{region} {subject} {learning_type} {salt}"  → "강남 수학 과외 강력 추천"
    "{salt} {region} {subject} {learning_type}"  → "검증된 강남 수학 과외"
    "{region} {target_audience} {subject} {salt}"→ "원주 성인 영어회화 추천"

{salt} 는 특수 토큰 — 위치에 따라 pool 이 결정된다:
    첫 번째 토큰 → prefix_salts
    마지막 토큰  → suffix_salts
    중간 토큰   → all_salts (prefix ∪ suffix)

Usage:
    gen = TitleGenerator(TitleOption(
        template = "{region} {subject} {learning_type} {salt}",
        values   = {"region": "강남", "subject": "수학", "learning_type": "과외"},
    ))
    title = gen.generate()  # e.g. "강남 수학 과외 강력 추천"
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from automator.options import TitleOption

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_PRESET_DIR          = Path(__file__).parent.parent / "presets" / "title"
_DEFAULT_SALT_PRESET = _PRESET_DIR / "salts.json"
_TOKEN_RE            = re.compile(r"\{(\w*)\}")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Preset file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_salts(path: str | Path = "") -> dict[str, list[str]]:
    """
    Load salt strings from salts.json.

    Returns dict with keys "prefix", "suffix", "all".
    """
    p      = Path(path) if path else _DEFAULT_SALT_PRESET
    raw    = _load_json(p)
    prefix = raw["prefix_salts"]
    suffix = raw["suffix_salts"]
    return {
        "prefix": prefix,
        "suffix": suffix,
        "all":    list(dict.fromkeys(prefix + suffix)),
    }


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

    Args:
        option: TitleOption with template, values, and optional salt_preset.
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
                # salt_preset 이 지정됐다면 template 을 쓰려는 의도 → 에러
                if option.salt_preset:
                    raise ValueError(
                        "template must not be empty when salt_preset is set. "
                        "Use fixed_title for a literal title, or provide a template."
                    )
                # salt_preset 도 없으면 TitleOption() 기본값 — 제목 없음으로 처리
                self._prefix_salts = []
                self._suffix_salts = []
                self._all_salts    = []
            else:
                validate_template(option.template)
                salt_data          = load_salts(option.salt_preset)
                self._prefix_salts = salt_data["prefix"]
                self._suffix_salts = salt_data["suffix"]
                self._all_salts    = salt_data["all"]

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
            sub["salt"] = self._rng.choice(self._pick_salt_pool(tokens))

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
