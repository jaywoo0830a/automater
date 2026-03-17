"""
factory/combo_generator.py
----------------------------
캠페인의 카테시안 곱을 생성해 combinations + combination_keywords 에 삽입.

스키마 v2 변경사항
------------------
- dimensions     → keyword_categories  (캠페인 독립 마스터)
- dimension_values → keywords          (캠페인 독립 마스터)
- campaign_slots   — 캠페인이 어떤 카테고리를 어떤 순서로 쓸지
- combination_values → combination_keywords

Usage:
    from factory.db import Database
    from factory.combo_generator import ComboGenerator

    with Database.from_env() as db:
        gen      = ComboGenerator(db=db, campaign_id=1)
        inserted = gen.run()
"""

from __future__ import annotations

import itertools
from typing import Any

# 캠페인이 사용하는 카테고리를 sort_order 순으로 조회
_FETCH_SLOTS_SQL = """
    SELECT cs.category_id, kc.slug, cs.sort_order
    FROM   campaign_slots      cs
    JOIN   keyword_categories  kc ON kc.id = cs.category_id
    WHERE  cs.campaign_id = %s
    ORDER  BY cs.sort_order
"""

# 카테고리의 모든 활성 키워드
_FETCH_KEYWORDS_SQL = """
    SELECT id, category_id
    FROM   keywords
    WHERE  category_id = %s
      AND  active = 1
    ORDER  BY sort_order, id
"""

# picks 로 필터링된 키워드
_FETCH_KEYWORDS_FILTERED_SQL = """
    SELECT id, category_id
    FROM   keywords
    WHERE  category_id = %s
      AND  active = 1
      AND  id IN ({placeholders})
    ORDER  BY sort_order, id
"""

_FETCH_SPACING_RULES_SQL = """
    SELECT id
    FROM   spacing_rules
    WHERE  campaign_id = %s
      AND  active = 1
"""

_FETCH_CAMPAIGN_CONFIG_SQL = """
    SELECT config FROM campaigns WHERE id = %s
"""

_INSERT_COMBO_SQL = """
    INSERT IGNORE INTO combinations (campaign_id, spacing_rule_id, config)
    VALUES (%s, %s, %s)
"""

_INSERT_COMBO_KEYWORDS_SQL = """
    INSERT IGNORE INTO combination_keywords (combination_id, keyword_id)
    VALUES (%s, %s)
"""

_CHUNK = 500


def build_combos(
    kw_groups: list[list[int]],
    spacing_rule_ids: list[int],
    has_suffix_options: list[int],
) -> list[dict]:
    """
    순수 카테시안 곱. DB 없이 테스트 가능.

    Args:
        kw_groups:          [[cat1_kw_ids], [cat2_kw_ids], ...]
                            campaign_slots 의 sort_order 순서
        spacing_rule_ids:   활성화된 spacing_rule id 목록
        has_suffix_options: [0, 1] — display_value vs value 선택

    Returns:
        List of dicts: keyword_ids, spacing_rule_id, has_suffix
    """
    combos = []
    for spacing_id, has_suffix in itertools.product(spacing_rule_ids, has_suffix_options):
        for combo_kws in itertools.product(*kw_groups):
            combos.append({
                "keyword_ids":     list(combo_kws),
                "spacing_rule_id": spacing_id,
                "has_suffix":      has_suffix,
            })
    return combos


class ComboGenerator:
    """
    캠페인의 조합을 생성해 DB 에 삽입.
    INSERT IGNORE — 멱등, 재실행 안전.

    Args:
        db:          Database instance.
        campaign_id: 대상 캠페인 id.
        picks:       {category_id: [keyword_id, ...] | None}
                     CampaignKeywordPicker.get_picked_keyword_ids() 반환값.
                     None 또는 키 없음 → 해당 카테고리 전체 키워드 사용.
                     빈 리스트 [] → 조합 생성 불가 (0 반환).
    """

    def __init__(self, db, campaign_id: int,
                 picks: dict[int, list[int] | None] | None = None) -> None:
        self._db          = db
        self._campaign_id = campaign_id
        self._picks       = picks or {}

    def run(self) -> int:
        """조합 생성 후 삽입. 실제 삽입된 수 반환."""
        import json

        row    = self._db.fetch_one(_FETCH_CAMPAIGN_CONFIG_SQL, (self._campaign_id,))
        config = json.loads(row["config"]) if row and row["config"] else {}
        has_suffix_options: list[int] = config.get("has_suffix_options", [0, 1])

        slots = self._db.fetch_all(_FETCH_SLOTS_SQL, (self._campaign_id,))
        if not slots:
            return 0

        kw_groups: list[list[int]] = []
        for slot in slots:
            cat_id  = slot["category_id"]
            picked  = self._picks.get(cat_id)  # None or list[int]

            if picked is not None and len(picked) == 0:
                return 0   # picks 가 비어있으면 조합 생성 불가

            if picked is not None:
                ph  = ", ".join(["%s"] * len(picked))
                kws = self._db.fetch_all(
                    _FETCH_KEYWORDS_FILTERED_SQL.format(placeholders=ph),
                    (cat_id, *picked),
                )
            else:
                kws = self._db.fetch_all(_FETCH_KEYWORDS_SQL, (cat_id,))

            if not kws:
                return 0
            kw_groups.append([k["id"] for k in kws])

        spacing_rows     = self._db.fetch_all(_FETCH_SPACING_RULES_SQL, (self._campaign_id,))
        spacing_rule_ids = [r["id"] for r in spacing_rows]
        if not spacing_rule_ids:
            return 0

        combos   = build_combos(kw_groups, spacing_rule_ids, has_suffix_options)
        inserted = 0

        for c in combos:
            self._db.execute(
                _INSERT_COMBO_SQL,
                (self._campaign_id,
                 c["spacing_rule_id"],
                 json.dumps({"has_suffix": c["has_suffix"]}))
            )
            combo_id = self._db.last_insert_id()
            if not combo_id:
                continue

            ck_rows = [(combo_id, kw_id) for kw_id in c["keyword_ids"]]
            self._db.execute_many(_INSERT_COMBO_KEYWORDS_SQL, ck_rows)
            inserted += 1

        return inserted
