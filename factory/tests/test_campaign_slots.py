"""
factory/tests/test_campaign_slots.py
--------------------------------------
ComboGenerator 단위 테스트.

스키마 v2 용어:
  campaign_slots      → 캠페인이 어떤 keyword_category 를 어떤 순서로 쓸지
  keyword_categories  → 키워드 카테고리 마스터 (region, subject, learning_type ...)
  keywords            → 실제 키워드 마스터 (강남구, 수학, 과외 ...)
  combinations        → 카테시안 곱 결과
  combination_keywords → combinations × keywords M:N 연결

DB 없이 순수 로직만 검증.
"""

import json
import pytest
from unittest.mock import MagicMock
from factory.combo_generator import ComboGenerator, build_combos


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _slots():
    """
    campaign_slots 행 구조.
    category_id + slug + sort_order — id 컬럼 없음.
    """
    return [
        {"category_id": 1, "slug": "region",        "sort_order": 0},
        {"category_id": 2, "slug": "subject",       "sort_order": 1},
        {"category_id": 3, "slug": "learning_type", "sort_order": 2},
    ]


def _keyword_map():
    """category_id → keywords 행 목록."""
    return {
        1: [{"id": 1, "category_id": 1}, {"id": 2, "category_id": 1}],  # 지역 2개
        2: [{"id": 3, "category_id": 2}, {"id": 4, "category_id": 2}],  # 과목 2개
        3: [{"id": 5, "category_id": 3}, {"id": 6, "category_id": 3}],  # 학습형태 2개
    }


def _spacing_rules():
    return [{"id": 10}, {"id": 20}, {"id": 30}]


def _mock_db(slots, keyword_map, spacing_rules, has_suffix_options=None):
    """
    slots:          campaign_slots 행 목록
    keyword_map:    {category_id: [keyword 행, ...]}
    spacing_rules:  spacing_rules 행 목록
    """
    db = MagicMock()
    config_json = json.dumps({"has_suffix_options": has_suffix_options or [0, 1]})
    db.fetch_one.return_value = {"config": config_json}
    db.fetch_all.side_effect = [
        slots,
        *[keyword_map[s["category_id"]] for s in slots],
        spacing_rules,
    ]
    _counter = [0]
    def _last_insert_id():
        _counter[0] += 1
        return _counter[0]
    db.last_insert_id.side_effect = _last_insert_id
    return db


# ---------------------------------------------------------------------------
# build_combos() — 순수 카테시안 곱
# ---------------------------------------------------------------------------

class TestBuildCombos:

    def test_total_count(self):
        """지역×과목×학습형태 × spacing_rules × has_suffix = 2×2×2×3×2 = 48"""
        combos = build_combos([[1, 2], [3, 4], [5, 6]], [10, 20, 30], [0, 1])
        assert len(combos) == 2 * 2 * 2 * 3 * 2

    def test_each_combo_has_required_keys(self):
        """각 조합 dict 에 keyword_ids, spacing_rule_id, has_suffix 가 있어야 한다."""
        combos = build_combos([[1], [2], [3]], [10], [0, 1])
        for combo in combos:
            assert {"keyword_ids", "spacing_rule_id", "has_suffix"} <= combo.keys()

    def test_no_duplicate_combos(self):
        """카테시안 곱에 중복 조합이 없어야 한다."""
        combos = build_combos([[1, 2], [3, 4], [5, 6]], [10, 20, 30], [0, 1])
        keys = [
            (tuple(c["keyword_ids"]), c["spacing_rule_id"], c["has_suffix"])
            for c in combos
        ]
        assert len(keys) == len(set(keys))

    def test_all_spacing_rules_represented(self):
        """모든 spacing_rule_id 가 결과에 포함되어야 한다."""
        combos = build_combos([[1], [2]], [10, 20, 30], [0])
        found  = {c["spacing_rule_id"] for c in combos}
        assert found == {10, 20, 30}

    def test_both_has_suffix_options_represented(self):
        """has_suffix 0, 1 이 모두 결과에 포함되어야 한다."""
        combos = build_combos([[1], [2]], [10], [0, 1])
        assert {c["has_suffix"] for c in combos} == {0, 1}

    def test_keyword_ids_order_matches_slot_sort_order(self):
        """keyword_ids 순서 = campaign_slots 의 sort_order 순서."""
        combos = build_combos([[100], [200], [300]], [10], [0])
        assert combos[0]["keyword_ids"] == [100, 200, 300]

    def test_empty_keyword_group_returns_empty(self):
        """한 카테고리 키워드가 비면 조합 불가 → 빈 리스트 반환."""
        assert build_combos([[], [1, 2]], [10], [0]) == []

    def test_empty_spacing_rules_returns_empty(self):
        """spacing_rules 가 없으면 조합 불가 → 빈 리스트 반환."""
        assert build_combos([[1], [2]], [], [0]) == []

    def test_single_has_suffix_option(self):
        """has_suffix 옵션이 하나면 모든 조합에 그 값만 사용된다."""
        combos = build_combos([[1], [2]], [10], [1])
        assert all(c["has_suffix"] == 1 for c in combos)


# ---------------------------------------------------------------------------
# ComboGenerator.run() — DB 조회·삽입 흐름
# ---------------------------------------------------------------------------

class TestComboGeneratorRun:

    def test_queries_campaign_slots_for_campaign(self):
        """첫 번째 fetch_all 이 campaign_slots 를 캠페인 id 로 조회해야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), _spacing_rules())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        first_call = db.fetch_all.call_args_list[0]
        assert "campaign_slots" in first_call.args[0].lower()
        assert first_call.args[1] == (1,)

    def test_queries_keywords_once_per_slot(self):
        """keywords 조회가 slot 수만큼 호출되고 active=1 조건이 포함되어야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), _spacing_rules())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        kw_calls = [
            c for c in db.fetch_all.call_args_list
            if "keywords" in c.args[0].lower()
        ]
        assert len(kw_calls) == len(_slots())
        for c in kw_calls:
            assert "active = 1" in c.args[0]

    def test_queries_active_spacing_rules(self):
        """spacing_rules 조회에 active=1 조건이 포함되어야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), _spacing_rules())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        sr_calls = [
            c for c in db.fetch_all.call_args_list
            if "spacing_rules" in c.args[0].lower()
        ]
        assert sr_calls
        assert "active = 1" in sr_calls[0].args[0]

    def test_inserts_combinations_with_insert_ignore(self):
        """combinations 삽입에 INSERT IGNORE 를 사용해야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), _spacing_rules())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        inserts = [
            c for c in db.execute.call_args_list
            if "combinations" in c.args[0].lower()
            and "combination_keywords" not in c.args[0].lower()
        ]
        assert inserts
        assert "INSERT IGNORE" in inserts[0].args[0].upper()

    def test_inserts_combination_keywords_with_insert_ignore(self):
        """combination_keywords 삽입에 INSERT IGNORE 를 사용해야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), _spacing_rules())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        inserts = [
            c for c in db.execute_many.call_args_list
            if "combination_keywords" in c.args[0].lower()
        ]
        assert inserts
        assert "INSERT IGNORE" in inserts[0].args[0].upper()

    def test_no_slots_skips_all_inserts(self):
        """campaign_slots 가 없으면 combinations 삽입이 없어야 한다."""
        db = _mock_db([], {}, [])
        db.fetch_one.return_value = {"config": "{}"}
        db.fetch_all.side_effect  = [[], []]
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        inserts = [
            c for c in db.execute.call_args_list
            if "combinations" in str(c).lower()
        ]
        assert not inserts

    def test_no_spacing_rules_skips_all_inserts(self):
        """spacing_rules 가 없으면 combinations 삽입이 없어야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), [])
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        inserts = [
            c for c in db.execute.call_args_list
            if "combinations" in str(c).lower()
        ]
        assert not inserts

    def test_has_suffix_stored_as_json_in_config_column(self):
        """combinations.config 컬럼에 has_suffix 값이 JSON 으로 저장되어야 한다."""
        db  = _mock_db(_slots(), _keyword_map(), [{"id": 10}])
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        inserts = [
            c for c in db.execute.call_args_list
            if "combinations" in c.args[0].lower()
            and "combination_keywords" not in c.args[0].lower()
        ]
        assert inserts
        for c in inserts:
            config = json.loads(c.args[1][2])
            assert "has_suffix" in config
