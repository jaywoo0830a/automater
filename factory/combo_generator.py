"""
factory/combo_generator.py
----------------------------
Generates the full cartesian product for a campaign and bulk-inserts
into combinations + combination_values.

모든 도메인 값은 DB 에서 읽어오므로 코드 변경 없이 과목/지역/학습형태 추가 가능.
띄어쓰기 패턴도 spacing_rules 테이블에서 읽어온다.

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

_FETCH_DIMENSIONS_SQL = """
    SELECT id, slug, sort_order
    FROM   dimensions
    WHERE  campaign_id = %s
    ORDER  BY sort_order
"""

_FETCH_DIM_VALUES_SQL = """
    SELECT id, dimension_id
    FROM   dimension_values
    WHERE  dimension_id = %s
      AND  active = 1
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

_INSERT_COMBO_VALUES_SQL = """
    INSERT IGNORE INTO combination_values (combination_id, dimension_value_id)
    VALUES (%s, %s)
"""

_CHUNK = 500


def build_combos(
    dim_value_groups: list[list[int]],
    spacing_rule_ids: list[int],
    has_suffix_options: list[int],
) -> list[dict]:
    """
    순수 카테시안 곱. DB 없이 테스트 가능.

    Args:
        dim_value_groups:   [[dim1_val_ids], [dim2_val_ids], ...]
                            dimensions 의 sort_order 순서
        spacing_rule_ids:   활성화된 spacing_rule id 목록
        has_suffix_options: [0, 1] — display_value vs value 선택

    Returns:
        List of dicts:
            dim_value_ids, spacing_rule_id, has_suffix
    """
    combos = []
    for spacing_id, has_suffix in itertools.product(spacing_rule_ids, has_suffix_options):
        for combo_values in itertools.product(*dim_value_groups):
            combos.append({
                "dim_value_ids":   list(combo_values),
                "spacing_rule_id": spacing_id,
                "has_suffix":      has_suffix,
            })
    return combos


class ComboGenerator:
    """
    캠페인의 모든 조합을 생성해 DB 에 삽입.
    INSERT IGNORE — 멱등, 재실행 안전.
    """

    def __init__(self, db, campaign_id: int) -> None:
        self._db          = db
        self._campaign_id = campaign_id

    def run(self) -> int:
        """조합 생성 후 삽입. 실제 삽입된 수 반환."""
        import json

        # 캠페인 config 에서 has_suffix_options 읽기 (기본: [0, 1])
        row = self._db.fetch_one(_FETCH_CAMPAIGN_CONFIG_SQL, (self._campaign_id,))
        config = json.loads(row["config"]) if row and row["config"] else {}
        has_suffix_options: list[int] = config.get("has_suffix_options", [0, 1])

        # 차원 목록 (sort_order 순)
        dimensions = self._db.fetch_all(_FETCH_DIMENSIONS_SQL, (self._campaign_id,))
        if not dimensions:
            return 0

        # 차원별 value id 목록
        dim_value_groups: list[list[int]] = []
        for dim in dimensions:
            values = self._db.fetch_all(_FETCH_DIM_VALUES_SQL, (dim["id"],))
            if not values:
                return 0  # 빈 차원이 있으면 조합 불가
            dim_value_groups.append([v["id"] for v in values])

        # 활성 spacing_rules
        spacing_rows    = self._db.fetch_all(_FETCH_SPACING_RULES_SQL, (self._campaign_id,))
        spacing_rule_ids = [r["id"] for r in spacing_rows]
        if not spacing_rule_ids:
            return 0

        combos   = build_combos(dim_value_groups, spacing_rule_ids, has_suffix_options)
        inserted = 0

        for c in combos:
            # combinations: 하나씩 INSERT — lastrowid 로 combination_values 연결
            # bulk INSERT IGNORE 는 lastrowid 가 마지막 행만 반환하므로 사용 불가
            self._db.execute(
                _INSERT_COMBO_SQL,
                (self._campaign_id,
                 c["spacing_rule_id"],
                 json.dumps({"has_suffix": c["has_suffix"]}))
            )
            combo_id = self._db.last_insert_id()
            if not combo_id:
                # INSERT IGNORE — 이미 존재하는 행은 lastrowid = 0, 건너뜀
                continue

            # combination_values: 이 조합이 어떤 dimension_value 들로 구성되는지
            cv_rows = [(combo_id, dv_id) for dv_id in c["dim_value_ids"]]
            self._db.execute_many(_INSERT_COMBO_VALUES_SQL, cv_rows)
            inserted += 1

        return inserted
