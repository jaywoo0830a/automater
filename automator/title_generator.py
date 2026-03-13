"""
automator/title_generator.py
-----------------------------
TitleGenerator: TitleOption → 제목 문자열

책임
----
- presets/title/{regions,subjects,salts}.json 에서 프리셋 로드
- TitleOption.template 에 따라 토큰을 조합해 제목 반환
- include_suffix 플래그에 따라 지역명 선택 (full_name or base_name)
- 스텁 기능(has_space, add_affix, randomize_chars, ai_preset_prompt)은
  현재 아무것도 하지 않으며, 호출되면 원문 그대로 반환한다.

Template 형식
-------------
    "지역+과목+학습형태+솔트"   → 기본 (솔트 맨 끝)
    "솔트+지역+과목+학습형태"   → 솔트 맨 앞
    "지역+솔트+과목+학습형태"   → 솔트 중간

    유효 토큰: 지역, 과목, 학습형태, 솔트 (네 개 모두 정확히 한 번씩 포함 필수)
    유효하지 않은 템플릿은 TitleGenerator 생성 시 ValueError를 발생시킨다.

Usage:
    from automator.title_generator import TitleGenerator
    from automator.options import TitleOption

    gen   = TitleGenerator(TitleOption(include_suffix=True))
    title = gen.generate()   # e.g. "대치동 영어 과외 강력 추천"
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from automator.options import TitleOption, TITLE_TOKENS

# ---------------------------------------------------------------------------
# Default preset paths
# ---------------------------------------------------------------------------

_PRESET_DIR = Path(__file__).parent.parent / "presets" / "title"

_DEFAULT_REGION_PRESET  = _PRESET_DIR / "regions.json"
_DEFAULT_SUBJECT_PRESET = _PRESET_DIR / "subjects.json"
_DEFAULT_SALT_PRESET    = _PRESET_DIR / "salts.json"


# ---------------------------------------------------------------------------
# Preset loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Preset file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_regions(path: str | Path = "") -> list[dict]:
    """
    Load region entries from a regions.json file.

    Each entry: {"base_name": str, "full_name": str, "tier": str}
    """
    p = Path(path) if path else _DEFAULT_REGION_PRESET
    return _load_json(p)["regions"]


def load_subjects(path: str | Path = "") -> list[str]:
    """Load subject strings from a subjects.json file."""
    p = Path(path) if path else _DEFAULT_SUBJECT_PRESET
    return _load_json(p)["subjects"]


def load_salts(path: str | Path = "") -> list[str]:
    """Load salt strings from a salts.json file."""
    p = Path(path) if path else _DEFAULT_SALT_PRESET
    return _load_json(p)["salts"]


# ---------------------------------------------------------------------------
# Template validation
# ---------------------------------------------------------------------------

def validate_template(template: str) -> None:
    """
    Raise ValueError if the template is not a valid token sequence.

    Rules:
      - Tokens are separated by '+'.
      - Must contain exactly the four tokens in TITLE_TOKENS.
      - Each token must appear exactly once.
      - Unknown tokens are rejected.

    Examples:
      ✅  "지역+과목+학습형태+솔트"
      ✅  "솔트+지역+과목+학습형태"
      ❌  "지역+과목+솔트"            (학습형태 누락)
      ❌  "지역+과목+학습형태+솔트+솔트" (솔트 중복)
      ❌  "지역+과목+학습형태+unknown"  (알 수 없는 토큰)
    """
    if not template or not template.strip():
        raise ValueError("template must not be empty")

    tokens = [t.strip() for t in template.split("+")]

    unknown = set(tokens) - TITLE_TOKENS
    if unknown:
        raise ValueError(
            f"Unknown token(s) in template: {unknown}. "
            f"Valid tokens: {TITLE_TOKENS}"
        )

    missing = TITLE_TOKENS - set(tokens)
    if missing:
        raise ValueError(
            f"Template is missing required token(s): {missing}"
        )

    duplicates = {t for t in tokens if tokens.count(t) > 1}
    if duplicates:
        raise ValueError(
            f"Template contains duplicate token(s): {duplicates}"
        )


# ---------------------------------------------------------------------------
# TitleGenerator
# ---------------------------------------------------------------------------

class TitleGenerator:
    """
    Generates a single blog post title from a TitleOption.

    Presets are loaded once on construction. generate() picks one entry
    from each preset at random and assembles them according to the template.

    Args:
        option: TitleOption describing assembly rules and preset paths.
        rng:    Optional random.Random for deterministic tests.

    Raises:
        ValueError: If the template is invalid (on construction).
        FileNotFoundError: If a preset file is missing (on construction).
    """

    def __init__(
        self,
        option: TitleOption,
        rng: random.Random | None = None,
    ) -> None:
        validate_template(option.template)

        self._opt      = option
        self._rng      = rng or random.Random()
        self._regions  = load_regions(option.region_preset)
        self._subjects = load_subjects(option.subject_preset)
        self._salts    = load_salts(option.salt_preset)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """
        Return the post title.

        If TitleOption.fixed_title is set, return it as-is without any
        preset lookup or assembly — useful for tests and one-off posts.

        Otherwise, pick one region, subject, and salt from presets and
        assemble them according to the template.

        e.g. "대치동 영어 과외 강력 추천"
             "강력 추천 대치동 영어 과외"  (솔트+지역+과목+학습형태)
        """
        if self._opt.fixed_title:
            return self._opt.fixed_title

        region  = self._pick_region()
        subject = self._rng.choice(self._subjects)
        salt    = self._rng.choice(self._salts)
        return self._assemble(region, subject, salt)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pick_region(self) -> str:
        """
        Pick a random region name respecting include_suffix.

        True  → full_name ("대치동") — 행정구역 단위 포함
        False → base_name ("대치")  — 행정구역 단위 제외
        """
        entry = self._rng.choice(self._regions)
        return entry["full_name"] if self._opt.include_suffix else entry["base_name"]

    def _assemble(self, region: str, subject: str, salt: str) -> str:
        """
        Map tokens to values and join in template order.

        Token map:
          지역       → region
          과목       → subject
          학습형태   → learning_type
          솔트       → salt
        """
        token_map = {
            "지역":     region,
            "과목":     subject,
            "학습형태": self._opt.learning_type,
            "솔트":     salt,
        }

        keys   = [t.strip() for t in self._opt.template.split("+")]
        tokens = [token_map[k] for k in keys]

        # has_space stub — currently always True
        sep   = " " if self._opt.has_space else ""
        title = sep.join(tokens)

        title = self._apply_affix(title)
        title = self._apply_randomize(title)
        return title

    # ------------------------------------------------------------------
    # Stub methods
    # ------------------------------------------------------------------

    def _apply_affix(self, title: str) -> str:
        """
        Stub: prepend/append a random Korean particle.
        add_affix=True would produce e.g. "대치동에서 영어 과외 강력 추천".
        Currently a no-op.
        """
        if not self._opt.add_affix:
            return title
        # TODO: implement Korean particle attachment
        return title

    def _apply_randomize(self, title: str) -> str:
        """
        Stub: substitute characters with visually similar lookalikes.
        Currently a no-op.
        """
        if not self._opt.randomize_chars:
            return title
        # TODO: implement lookalike character substitution
        return title
