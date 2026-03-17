"""
factory/keyword_picker.py
--------------------------
CampaignKeywordPicker — campaign_keyword_picks 를 관리한다.

동작 방식
----------
- 덮어쓰기: pick() 호출 시 해당 카테고리의 기존 picks 를 DELETE 후 INSERT.
- 빈 리스트: 해당 카테고리 picks 를 전부 제거 → seed 시 전체 키워드 사용.
- picks 없음: ComboGenerator 는 해당 카테고리의 모든 active 키워드를 사용.

Usage:
    from factory.db import Database
    from factory.keyword_picker import CampaignKeywordPicker

    with Database.from_env() as db:
        picker = CampaignKeywordPicker(db=db, campaign_id=1)

        # 지역을 강남구·수원시로 제한
        picker.pick(category_slug="region", values=["강남구", "수원시"])

        # 현재 선택 확인
        print(picker.list_picks())
        # → {"region": ["강남구", "수원시"], "subject": [], "learning_type": []}

        # combo_generator 에 전달할 id 목록
        print(picker.get_picked_keyword_ids())
        # → {1: [10, 11], 2: None, 3: None}
"""

from __future__ import annotations


_FETCH_SLOTS_SQL = """
    SELECT cs.category_id, kc.slug, cs.sort_order
    FROM   campaign_slots      cs
    JOIN   keyword_categories  kc ON kc.id = cs.category_id
    WHERE  cs.campaign_id = %s
    ORDER  BY cs.sort_order
"""

_FETCH_ALL_KEYWORDS_SQL = """
    SELECT k.id, k.category_id, k.value
    FROM   keywords       k
    JOIN   campaign_slots cs ON cs.category_id = k.category_id
    WHERE  cs.campaign_id = %s
      AND  k.active = 1
"""

_FETCH_PICKS_SQL = """
    SELECT ckp.category_id, kc.slug, k.value
    FROM   campaign_keyword_picks ckp
    JOIN   keyword_categories     kc ON kc.id = ckp.category_id
    JOIN   keywords               k  ON k.id  = ckp.keyword_id
    WHERE  ckp.campaign_id = %s
    ORDER  BY cs.sort_order, k.sort_order, k.id
"""

_FETCH_PICKS_SQL = """
    SELECT ckp.category_id, kc.slug, ckp.keyword_id, k.value
    FROM   campaign_keyword_picks ckp
    JOIN   keyword_categories     kc  ON kc.id  = ckp.category_id
    JOIN   keywords               k   ON k.id   = ckp.keyword_id
    JOIN   campaign_slots         cs  ON cs.campaign_id = ckp.campaign_id
                                     AND cs.category_id = ckp.category_id
    WHERE  ckp.campaign_id = %s
    ORDER  BY cs.sort_order, k.sort_order, k.id
"""

_DELETE_PICKS_SQL = """
    DELETE FROM campaign_keyword_picks
    WHERE  campaign_id = %s
      AND  category_id = %s
"""

_INSERT_PICK_SQL = """
    INSERT IGNORE INTO campaign_keyword_picks
        (campaign_id, category_id, keyword_id)
    VALUES (%s, %s, %s)
"""


class CampaignKeywordPicker:
    """
    캠페인의 keyword picks 를 관리한다.

    Args:
        db:          Database instance.
        campaign_id: 대상 캠페인 id.
    """

    def __init__(self, db, campaign_id: int) -> None:
        self._db          = db
        self._campaign_id = campaign_id

    # ------------------------------------------------------------------
    # picks 저장
    # ------------------------------------------------------------------

    def pick(self, category_slug: str, values: list[str]) -> int:
        """
        category_slug 에 해당하는 카테고리의 picks 를 덮어쓴다.

        Args:
            category_slug: 카테고리 식별자 ('region', 'subject', ...)
            values:        선택할 키워드 목록 (e.g. ["강남구", "수원시"])
                           빈 리스트면 picks 를 전부 제거 (전체 사용).

        Returns:
            실제 선택된 키워드 수.

        Raises:
            ValueError: category_slug 가 없거나 values 안에 없는 키워드가 있을 때.
        """
        slots = self._db.fetch_all(_FETCH_SLOTS_SQL, (self._campaign_id,))
        slot  = next((s for s in slots if s["slug"] == category_slug), None)
        if slot is None:
            raise ValueError(
                f"category slug '{category_slug}' 없음. "
                f"사용 가능: {[s['slug'] for s in slots]}"
            )

        cat_id = slot["category_id"]

        if values:
            all_kws = self._db.fetch_all(_FETCH_ALL_KEYWORDS_SQL, (self._campaign_id,))
            cat_kws = {kw["value"]: kw["id"] for kw in all_kws if kw["category_id"] == cat_id}

            unknown = [v for v in values if v not in cat_kws]
            if unknown:
                raise ValueError(
                    f"없는 키워드: {unknown}. "
                    f"'{category_slug}' 에서 사용 가능한 값: {list(cat_kws.keys())}"
                )

            selected_ids = [cat_kws[v] for v in values]
        else:
            selected_ids = []

        self._db.execute(_DELETE_PICKS_SQL, (self._campaign_id, cat_id))

        if selected_ids:
            rows = [(self._campaign_id, cat_id, kw_id) for kw_id in selected_ids]
            self._db.execute_many(_INSERT_PICK_SQL, rows)

        return len(selected_ids)

    # ------------------------------------------------------------------
    # picks 조회
    # ------------------------------------------------------------------

    def list_picks(self) -> dict[str, list[str]]:
        """
        현재 picks 현황을 반환한다.

        Returns:
            {category_slug: [picked_value, ...]}
            picks 없는 카테고리는 [] (전체 사용).
        """
        slots = self._db.fetch_all(_FETCH_SLOTS_SQL, (self._campaign_id,))
        rows  = self._db.fetch_all(_FETCH_PICKS_SQL, (self._campaign_id,))

        result: dict[str, list[str]] = {s["slug"]: [] for s in slots}
        for row in rows:
            result[row["slug"]].append(row["value"])
        return result

    def get_picked_keyword_ids(self) -> dict[int, list[int] | None]:
        """
        ComboGenerator 에서 사용할 category_id → [keyword_id, ...] 매핑.

        Returns:
            {category_id: [keyword_id, ...] | None}
            None = 해당 카테고리 picks 없음 → 전체 키워드 사용.
        """
        slots = self._db.fetch_all(_FETCH_SLOTS_SQL, (self._campaign_id,))
        rows  = self._db.fetch_all(_FETCH_PICKS_SQL, (self._campaign_id,))

        result: dict[int, list[int] | None] = {s["category_id"]: None for s in slots}
        for row in rows:
            cat_id = row["category_id"]
            if result[cat_id] is None:
                result[cat_id] = []
            result[cat_id].append(row["keyword_id"])
        return result
