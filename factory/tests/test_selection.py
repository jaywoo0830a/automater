"""
factory/tests/test_selection.py
---------------------------------
Unit tests for CampaignSelector.

DB 없이 순수 로직만 검증.
"""

import pytest
from unittest.mock import MagicMock, call
from factory.keyword_picker import CampaignKeywordPicker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dims():
    return [
        {"id": 1, "slug": "region",        "sort_order": 0},
        {"id": 2, "slug": "subject",       "sort_order": 1},
        {"id": 3, "slug": "learning_type", "sort_order": 2},
    ]


def _dv(id_, dim_id, value):
    return {"id": id_, "category_id": dim_id, "value": value}


def _all_dvs():
    return [
        _dv(1, 1, "강남구"), _dv(2, 1, "수원시"), _dv(3, 1, "성남시"),
        _dv(4, 2, "수학"),   _dv(5, 2, "영어"),
        _dv(6, 3, "과외"),   _dv(7, 3, "학원"),
    ]


def _mock_db(dims=None, dvs=None, existing=None):
    db = MagicMock()
    db.fetch_all.side_effect = [
        dims  or _dims(),
        dvs   or _all_dvs(),
        existing or [],
    ]
    return db


# ---------------------------------------------------------------------------
# select() — 덮어쓰기 방식
# ---------------------------------------------------------------------------

class TestSelect:

    def test_select_deletes_existing_then_inserts(self):
        """기존 선택을 DELETE 후 새 값 INSERT."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구", "수원시"])

        # DELETE 호출 확인
        delete_calls = [c for c in db.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert delete_calls, "DELETE 미호출"

        # INSERT 호출 확인
        insert_calls = [c for c in db.execute_many.call_args_list
                        if "campaign_keyword_picks" in str(c).lower()]
        assert insert_calls, "INSERT 미호출"

    def test_select_inserts_correct_value_ids(self):
        """선택한 value 에 해당하는 keyword_id 만 INSERT."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구", "수원시"])

        insert_call = [c for c in db.execute_many.call_args_list
                       if "campaign_keyword_picks" in str(c).lower()][0]
        rows = insert_call.args[1]
        inserted_dv_ids = {row[2] for row in rows}   # (campaign_id, dim_id, dv_id)
        assert inserted_dv_ids == {1, 2}             # 강남구=1, 수원시=2

    def test_select_unknown_value_raises(self):
        """없는 값을 선택하면 ValueError."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        with pytest.raises(ValueError, match="없는 값"):
            sel.pick(category_slug="region", values=["없는동네"])

    def test_select_unknown_dimension_raises(self):
        """없는 dimension slug 를 선택하면 ValueError."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        with pytest.raises(ValueError, match="dimension"):
            sel.pick(category_slug="unknown_dim", values=["강남구"])

    def test_select_empty_values_clears_selection(self):
        """빈 리스트를 선택하면 해당 dimension 선택이 전부 제거된다 (전체 사용)."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=[])

        delete_calls = [c for c in db.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert delete_calls, "DELETE 미호출"
        insert_calls = [c for c in db.execute_many.call_args_list
                        if "campaign_keyword_picks" in str(c).lower()]
        assert not insert_calls, "빈 선택인데 INSERT 됨"

    def test_select_is_overwrite_not_accumulate(self):
        """두 번 select 하면 마지막 값만 남는다 (덮어쓰기)."""
        # 첫 번째 select
        db1 = _mock_db()
        sel = CampaignKeywordPicker(db=db1, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구"])

        # 두 번째 select — DB mock 재설정
        db1.fetch_all.side_effect = [_dims(), _all_dvs(), []]
        sel.pick(category_slug="region", values=["수원시"])

        # 두 번 DELETE 가 호출됐어야 함
        delete_calls = [c for c in db1.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert len(delete_calls) == 2

    def test_select_returns_selected_count(self):
        """select() 는 실제 선택된 값 수를 반환한다."""
        db = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        count = sel.pick(category_slug="region", values=["강남구", "수원시"])
        assert count == 2


# ---------------------------------------------------------------------------
# list_picks() — 현재 선택 조회
# ---------------------------------------------------------------------------

class TestListSelections:

    def test_list_returns_per_dimension_dict(self):
        """
        {dimension_slug: [value, ...]} 형태로 반환.
        선택 없는 dimension 은 [] (전체 사용).
        """
        db = MagicMock()
        db.fetch_all.side_effect = [
            _dims(),
            # campaign_keyword_picks JOIN dimension_values
            [
                {"category_id": 1, "slug": "region",  "value": "강남구"},
                {"category_id": 1, "slug": "region",  "value": "수원시"},
                {"category_id": 2, "slug": "subject",  "value": "수학"},
            ],
        ]
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.list_picks()

        assert result["region"]        == ["강남구", "수원시"]
        assert result["subject"]       == ["수학"]
        assert result["learning_type"] == []   # 선택 없음 → 전체 사용

    def test_list_no_selections_returns_all_empty(self):
        """선택이 하나도 없으면 모든 dimension 이 []."""
        db = MagicMock()
        db.fetch_all.side_effect = [_dims(), []]
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.list_picks()
        assert all(v == [] for v in result.values())


# ---------------------------------------------------------------------------
# get_picked_keyword_ids() — combo_generator 연동용
# ---------------------------------------------------------------------------

class TestGetSelectedValueIds:

    def test_selected_dimension_returns_selected_ids(self):
        """선택이 있는 dimension 은 선택된 id 목록만 반환."""
        db = MagicMock()
        db.fetch_all.side_effect = [
            _dims(),
            [
                {"category_id": 1, "slug": "region", "dv_id": 1, "value": "강남구"},
                {"category_id": 1, "slug": "region", "dv_id": 2, "value": "수원시"},
            ],
        ]
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.get_picked_keyword_ids()

        assert result[1] == [1, 2]    # category_id=1 → [강남구, 수원시]

    def test_unselected_dimension_returns_none(self):
        """선택이 없는 dimension 은 None → combo_generator 가 전체를 사용."""
        db = MagicMock()
        db.fetch_all.side_effect = [_dims(), []]
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.get_picked_keyword_ids()

        assert all(v is None for v in result.values())
