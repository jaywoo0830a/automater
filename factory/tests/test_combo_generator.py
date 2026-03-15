"""
factory/tests/test_combo_generator.py
---------------------------------------
Unit tests for ComboGenerator.

DB 없이 순수 로직만 검증.
"""

import json
import pytest
from unittest.mock import MagicMock, call
from factory.combo_generator import ComboGenerator, build_combos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db(dimensions, dim_values_map, spacing_rules, has_suffix_options=None):
    """
    dimensions:     [{"id":1,"slug":"region","sort_order":0}, ...]
    dim_values_map: {dim_id: [{"id":1,"dimension_id":1}, ...]}
    spacing_rules:  [{"id":10}, {"id":20}]
    """
    db = MagicMock()
    config_json = json.dumps({"has_suffix_options": has_suffix_options or [0, 1]})
    db.fetch_one.return_value = {"config": config_json}
    db.fetch_all.side_effect = [
        dimensions,
        *[dim_values_map[d["id"]] for d in dimensions],
        spacing_rules,
    ]
    # last_insert_id: 첫 번째 호출부터 순차적으로 1, 2, 3 ... 반환
    _counter = [0]
    def _last_insert_id():
        _counter[0] += 1
        return _counter[0]
    db.last_insert_id.side_effect = _last_insert_id
    return db


def _dims():
    return [
        {"id": 1, "slug": "region",        "sort_order": 0},
        {"id": 2, "slug": "subject",       "sort_order": 1},
        {"id": 3, "slug": "learning_type", "sort_order": 2},
    ]


def _dv_map():
    return {
        1: [{"id": 1, "dimension_id": 1}, {"id": 2, "dimension_id": 1}],  # 2 regions
        2: [{"id": 3, "dimension_id": 2}, {"id": 4, "dimension_id": 2}],  # 2 subjects
        3: [{"id": 5, "dimension_id": 3}, {"id": 6, "dimension_id": 3}],  # 2 lt
    }


def _spacing():
    return [{"id": 10}, {"id": 20}, {"id": 30}]


# ---------------------------------------------------------------------------
# build_combos() — 순수 카테시안 곱
# ---------------------------------------------------------------------------

class TestBuildCombos:

    def test_total_count(self):
        """regions×subjects×lt × spacing × suffix = 2×2×2 × 3 × 2 = 48"""
        combos = build_combos([[1,2],[3,4],[5,6]], [10,20,30], [0,1])
        assert len(combos) == 2*2*2*3*2

    def test_required_keys(self):
        combos = build_combos([[1],[2],[3]], [10], [0,1])
        for c in combos:
            assert {"dim_value_ids","spacing_rule_id","has_suffix"} <= c.keys()

    def test_no_duplicates(self):
        combos = build_combos([[1,2],[3,4],[5,6]], [10,20,30], [0,1])
        keys   = [(tuple(c["dim_value_ids"]), c["spacing_rule_id"], c["has_suffix"])
                  for c in combos]
        assert len(keys) == len(set(keys))

    def test_all_spacing_rules_present(self):
        combos = build_combos([[1],[2]], [10,20,30], [0])
        found  = {c["spacing_rule_id"] for c in combos}
        assert found == {10, 20, 30}

    def test_both_suffix_options_present(self):
        combos = build_combos([[1],[2]], [10], [0, 1])
        values = {c["has_suffix"] for c in combos}
        assert values == {0, 1}

    def test_dim_value_ids_order_matches_sort_order(self):
        """dim_value_ids 의 순서 = dimensions 의 sort_order"""
        combos = build_combos([[100],[200],[300]], [10], [0])
        assert combos[0]["dim_value_ids"] == [100, 200, 300]

    def test_empty_dim_group_returns_empty(self):
        assert build_combos([[], [1,2]], [10], [0]) == []

    def test_empty_spacing_rules_returns_empty(self):
        assert build_combos([[1],[2]], [], [0]) == []

    def test_single_suffix_option(self):
        combos = build_combos([[1],[2]], [10], [1])
        assert all(c["has_suffix"] == 1 for c in combos)


# ---------------------------------------------------------------------------
# ComboGenerator.run() — DB 연동 흐름
# ---------------------------------------------------------------------------

class TestComboGeneratorRun:

    def test_fetches_dimensions_for_campaign(self):
        db  = _mock_db(_dims(), _dv_map(), _spacing())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        dim_call = db.fetch_all.call_args_list[0]
        assert "dimensions" in dim_call.args[0].lower()
        assert dim_call.args[1] == (1,)

    def test_fetches_active_dim_values(self):
        db  = _mock_db(_dims(), _dv_map(), _spacing())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        # dimension_values 조회가 dimensions 수만큼 호출
        dv_calls = [c for c in db.fetch_all.call_args_list
                    if "dimension_values" in c.args[0].lower()]
        assert len(dv_calls) == len(_dims())
        for call_ in dv_calls:
            assert "active = 1" in call_.args[0]

    def test_fetches_active_spacing_rules(self):
        db  = _mock_db(_dims(), _dv_map(), _spacing())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        sr_call = [c for c in db.fetch_all.call_args_list
                   if "spacing_rules" in c.args[0].lower()]
        assert len(sr_call) >= 1
        assert "active = 1" in sr_call[0].args[0]

    def test_uses_insert_ignore_for_combinations(self):
        db  = _mock_db(_dims(), _dv_map(), _spacing())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        combo_inserts = [c for c in db.execute.call_args_list
                         if "combinations" in c.args[0].lower()
                         and "combination_values" not in c.args[0].lower()]
        assert combo_inserts
        assert "INSERT IGNORE" in combo_inserts[0].args[0].upper()

    def test_uses_insert_ignore_for_combination_values(self):
        db  = _mock_db(_dims(), _dv_map(), _spacing())
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        cv_inserts = [c for c in db.execute_many.call_args_list
                      if "combination_values" in c.args[0].lower()]
        assert cv_inserts
        assert "INSERT IGNORE" in cv_inserts[0].args[0].upper()

    def test_no_dimensions_skips_insert(self):
        db = _mock_db([], {}, [])
        db.fetch_one.return_value = {"config": "{}"}
        db.fetch_all.side_effect = [[], []]
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        combo_inserts = [c for c in db.execute.call_args_list
                         if "combinations" in str(c).lower()]
        assert not combo_inserts

    def test_no_spacing_rules_skips_insert(self):
        db = _mock_db(_dims(), _dv_map(), [])
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        combo_inserts = [c for c in db.execute.call_args_list
                         if "combinations" in str(c).lower()]
        assert not combo_inserts

    def test_has_suffix_stored_in_config_json(self):
        db  = _mock_db(_dims(), _dv_map(), [{"id": 10}])
        gen = ComboGenerator(db=db, campaign_id=1)
        gen.run()
        combo_inserts = [c for c in db.execute.call_args_list
                         if "combinations" in c.args[0].lower()
                         and "combination_values" not in c.args[0].lower()]
        assert combo_inserts
        # config 컬럼 (3번째 파라미터)이 JSON 형식이어야 함
        for call_ in combo_inserts:
            parsed = json.loads(call_.args[1][2])
            assert "has_suffix" in parsed
