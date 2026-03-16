"""
factory/selection.py
----------------------
CampaignSelector — dimension 별 선택 값을 DB 에 저장·조회한다.

동작 방식
----------
- 덮어쓰기: select() 호출 시 해당 dimension 의 기존 선택을 DELETE 후 INSERT.
- 빈 리스트: 해당 dimension 선택을 전부 제거 → seed 시 전체 값 사용.
- 선택 없음: combo_generator 는 해당 dimension 의 모든 active 값을 사용.

Usage:
    from factory.db import Database
    from factory.selection import CampaignSelector

    with Database.from_env() as db:
        sel = CampaignSelector(db=db, campaign_id=1)

        # 지역을 강남구·수원시로 덮어쓰기
        sel.select(dimension_slug="region", values=["강남구", "수원시"])

        # 현재 선택 확인
        print(sel.list_selections())
        # → {"region": ["강남구", "수원시"], "subject": [], "learning_type": []}

        # combo_generator 에 전달할 id 목록 (None = 전체 사용)
        print(sel.get_selected_value_ids())
        # → {1: [10, 11], 2: None, 3: None}
"""

from __future__ import annotations


_FETCH_DIMS_SQL = """
    SELECT id, slug, sort_order
    FROM   dimensions
    WHERE  campaign_id = %s
    ORDER  BY sort_order
"""

_FETCH_ALL_DVS_SQL = """
    SELECT dv.id, dv.dimension_id, dv.value
    FROM   dimension_values dv
    JOIN   dimensions d ON d.id = dv.dimension_id
    WHERE  d.campaign_id = %s
      AND  dv.active = 1
"""

_FETCH_SELECTIONS_SQL = """
    SELECT cs.dimension_id, d.slug, dv.value
    FROM   campaign_selections cs
    JOIN   dimensions       d  ON d.id  = cs.dimension_id
    JOIN   dimension_values dv ON dv.id = cs.dimension_value_id
    WHERE  cs.campaign_id = %s
    ORDER  BY d.sort_order, dv.sort_order, dv.id
"""

_FETCH_SELECTIONS_WITH_ID_SQL = """
    SELECT cs.dimension_id, d.slug, cs.dimension_value_id AS dv_id, dv.value
    FROM   campaign_selections cs
    JOIN   dimensions       d  ON d.id  = cs.dimension_id
    JOIN   dimension_values dv ON dv.id = cs.dimension_value_id
    WHERE  cs.campaign_id = %s
    ORDER  BY d.sort_order, dv.sort_order, dv.id
"""

_DELETE_DIM_SELECTIONS_SQL = """
    DELETE FROM campaign_selections
    WHERE  campaign_id  = %s
      AND  dimension_id = %s
"""

_INSERT_SELECTION_SQL = """
    INSERT IGNORE INTO campaign_selections (campaign_id, dimension_id, dimension_value_id)
    VALUES (%s, %s, %s)
"""


class CampaignSelector:
    """
    캠페인별 dimension 선택 값을 관리한다.

    Args:
        db:          Database instance.
        campaign_id: 대상 캠페인 id.
    """

    def __init__(self, db, campaign_id: int) -> None:
        self._db          = db
        self._campaign_id = campaign_id

    # ------------------------------------------------------------------
    # 선택 저장
    # ------------------------------------------------------------------

    def select(self, dimension_slug: str, values: list[str]) -> int:
        """
        dimension_slug 에 해당하는 dimension 의 선택을 덮어쓴다.

        Args:
            dimension_slug: 차원 식별자 ('region', 'subject', 'learning_type' 등)
            values:         선택할 값 목록 (e.g. ["강남구", "수원시"])
                            빈 리스트면 해당 dimension 선택을 전부 제거 (전체 사용).

        Returns:
            실제 선택된 값 수.

        Raises:
            ValueError: dimension_slug 가 존재하지 않거나 values 안에 없는 값이 있을 때.
        """
        dims = self._db.fetch_all(_FETCH_DIMS_SQL, (self._campaign_id,))
        dim  = next((d for d in dims if d["slug"] == dimension_slug), None)
        if dim is None:
            raise ValueError(
                f"dimension slug '{dimension_slug}' 없음. "
                f"사용 가능: {[d['slug'] for d in dims]}"
            )

        dim_id = dim["id"]

        if values:
            # 해당 dimension 의 모든 값을 로드해서 입력값 검증
            all_dvs = self._db.fetch_all(_FETCH_ALL_DVS_SQL, (self._campaign_id,))
            dim_dvs = {dv["value"]: dv["id"] for dv in all_dvs if dv["dimension_id"] == dim_id}

            unknown = [v for v in values if v not in dim_dvs]
            if unknown:
                raise ValueError(
                    f"없는 값: {unknown}. "
                    f"'{dimension_slug}' 에서 사용 가능한 값: {list(dim_dvs.keys())}"
                )

            selected_ids = [dim_dvs[v] for v in values]
        else:
            self._db.fetch_all(_FETCH_ALL_DVS_SQL, (self._campaign_id,))  # side_effect 소비
            selected_ids = []

        # 덮어쓰기: 기존 삭제 후 새로 INSERT
        self._db.execute(_DELETE_DIM_SELECTIONS_SQL, (self._campaign_id, dim_id))

        if selected_ids:
            rows = [(self._campaign_id, dim_id, dv_id) for dv_id in selected_ids]
            self._db.execute_many(_INSERT_SELECTION_SQL, rows)

        return len(selected_ids)

    # ------------------------------------------------------------------
    # 선택 조회
    # ------------------------------------------------------------------

    def list_selections(self) -> dict[str, list[str]]:
        """
        현재 선택 현황을 반환한다.

        Returns:
            {dimension_slug: [selected_value, ...]}
            선택이 없는 dimension 은 [] (전체 사용).
        """
        dims = self._db.fetch_all(_FETCH_DIMS_SQL, (self._campaign_id,))
        rows = self._db.fetch_all(_FETCH_SELECTIONS_SQL, (self._campaign_id,))

        result: dict[str, list[str]] = {d["slug"]: [] for d in dims}
        for row in rows:
            result[row["slug"]].append(row["value"])
        return result

    def get_selected_value_ids(self) -> dict[int, list[int] | None]:
        """
        combo_generator 에서 사용할 dimension_id → [dv_id, ...] 매핑을 반환한다.

        Returns:
            {dimension_id: [dv_id, ...] | None}
            None 은 해당 dimension 선택 없음 → 전체 값 사용.
        """
        dims = self._db.fetch_all(_FETCH_DIMS_SQL, (self._campaign_id,))
        rows = self._db.fetch_all(_FETCH_SELECTIONS_WITH_ID_SQL, (self._campaign_id,))

        result: dict[int, list[int] | None] = {d["id"]: None for d in dims}
        for row in rows:
            dim_id = row["dimension_id"]
            if result[dim_id] is None:
                result[dim_id] = []
            result[dim_id].append(row["dv_id"])
        return result
