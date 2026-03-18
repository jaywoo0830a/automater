"""
factory/tests/test_keyword_picker.py
--------------------------------------
CampaignKeywordPicker 단위 테스트.

스키마 v2 용어:
  campaign_slots          → 캠페인이 사용하는 keyword_category 선언
  keyword_categories      → 카테고리 마스터 (region, subject, learning_type)
  keywords                → 키워드 마스터 (강남구, 수학, 과외 ...)
  campaign_keyword_picks  → 이번 seed 에 포함할 키워드 선택 (원본 불변)

DB 없이 순수 로직만 검증.
"""

import pytest
from unittest.mock import MagicMock
from factory.keyword_picker import CampaignKeywordPicker


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _slots():
    """campaign_slots 행 구조 — category_id + slug + sort_order."""
    return [
        {"category_id": 1, "slug": "region",        "sort_order": 0},
        {"category_id": 2, "slug": "subject",       "sort_order": 1},
        {"category_id": 3, "slug": "learning_type", "sort_order": 2},
    ]


def _keyword(id_, category_id, value):
    return {"id": id_, "category_id": category_id, "value": value}


def _all_keywords():
    return [
        _keyword(1, 1, "강남구"), _keyword(2, 1, "수원시"), _keyword(3, 1, "성남시"),
        _keyword(4, 2, "수학"),   _keyword(5, 2, "영어"),
        _keyword(6, 3, "과외"),   _keyword(7, 3, "학원"),
    ]


def _mock_db(slots=None, keywords=None, existing_picks=None):
    db = MagicMock()
    db.fetch_all.side_effect = [
        slots          or _slots(),
        keywords       or _all_keywords(),
        existing_picks or [],
    ]
    return db


# ---------------------------------------------------------------------------
# pick() — 덮어쓰기 방식
# ---------------------------------------------------------------------------

class TestPick:

    def test_pick_deletes_existing_picks_before_inserting(self):
        """기존 campaign_keyword_picks 를 DELETE 후 새 picks 를 INSERT 한다."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구", "수원시"])

        delete_calls = [c for c in db.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert delete_calls, "DELETE 가 호출되지 않았습니다"

        insert_calls = [c for c in db.execute_many.call_args_list
                        if "campaign_keyword_picks" in str(c).lower()]
        assert insert_calls, "INSERT 가 호출되지 않았습니다"

    def test_pick_inserts_correct_keyword_ids(self):
        """선택한 value 에 해당하는 keyword_id 만 campaign_keyword_picks 에 INSERT 한다."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구", "수원시"])

        insert_call = [c for c in db.execute_many.call_args_list
                       if "campaign_keyword_picks" in str(c).lower()][0]
        rows = insert_call.args[1]
        inserted_keyword_ids = {row[2] for row in rows}  # (campaign_id, category_id, keyword_id)
        assert inserted_keyword_ids == {1, 2}            # 강남구=1, 수원시=2

    def test_pick_unknown_keyword_raises_value_error(self):
        """keywords 에 없는 값을 선택하면 ValueError 를 발생시킨다."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        with pytest.raises(ValueError, match="없는 키워드"):
            sel.pick(category_slug="region", values=["없는동네"])

    def test_pick_unknown_category_slug_raises_value_error(self):
        """campaign_slots 에 없는 category_slug 를 지정하면 ValueError 를 발생시킨다."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        with pytest.raises(ValueError, match="category"):
            sel.pick(category_slug="nonexistent", values=["강남구"])

    def test_pick_empty_values_clears_picks_for_category(self):
        """빈 리스트를 전달하면 해당 카테고리의 picks 가 제거된다 (전체 키워드 사용)."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=[])

        delete_calls = [c for c in db.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert delete_calls, "DELETE 가 호출되지 않았습니다"

        insert_calls = [c for c in db.execute_many.call_args_list
                        if "campaign_keyword_picks" in str(c).lower()]
        assert not insert_calls, "빈 선택인데 INSERT 가 호출됐습니다"

    def test_pick_is_overwrite_not_accumulate(self):
        """같은 카테고리에 두 번 pick 하면 이전 선택이 완전히 교체된다."""
        db  = _mock_db()
        sel = CampaignKeywordPicker(db=db, campaign_id=1)
        sel.pick(category_slug="region", values=["강남구"])

        db.fetch_all.side_effect = [_slots(), _all_keywords(), []]
        sel.pick(category_slug="region", values=["수원시"])

        delete_calls = [c for c in db.execute.call_args_list
                        if "DELETE" in str(c).upper()]
        assert len(delete_calls) == 2, "두 번 pick 하면 DELETE 가 두 번 호출되어야 합니다"

    def test_pick_returns_number_of_selected_keywords(self):
        """pick() 은 실제로 선택된 키워드 수를 반환한다."""
        db    = _mock_db()
        sel   = CampaignKeywordPicker(db=db, campaign_id=1)
        count = sel.pick(category_slug="region", values=["강남구", "수원시"])
        assert count == 2


# ---------------------------------------------------------------------------
# list_picks() — 현재 선택 조회
# ---------------------------------------------------------------------------

class TestListPicks:

    def test_list_picks_returns_per_category_dict(self):
        """
        {category_slug: [keyword_value, ...]} 형태로 반환한다.
        picks 없는 카테고리는 [] (= 전체 키워드 사용).
        """
        db = MagicMock()
        db.fetch_all.side_effect = [
            _slots(),
            [
                {"category_id": 1, "slug": "region",  "value": "강남구"},
                {"category_id": 1, "slug": "region",  "value": "수원시"},
                {"category_id": 2, "slug": "subject",  "value": "수학"},
            ],
        ]
        sel    = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.list_picks()

        assert result["region"]        == ["강남구", "수원시"]
        assert result["subject"]       == ["수학"]
        assert result["learning_type"] == []   # picks 없음 → 전체 사용

    def test_list_picks_no_picks_returns_all_empty_lists(self):
        """picks 가 없으면 모든 카테고리가 [] 로 반환된다."""
        db = MagicMock()
        db.fetch_all.side_effect = [_slots(), []]
        sel    = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.list_picks()
        assert all(v == [] for v in result.values())


# ---------------------------------------------------------------------------
# get_picked_keyword_ids() — ComboGenerator 연동용
# ---------------------------------------------------------------------------

class TestGetPickedKeywordIds:

    def test_picked_category_returns_selected_keyword_ids(self):
        """picks 가 있는 카테고리는 선택된 keyword_id 목록을 반환한다."""
        db = MagicMock()
        db.fetch_all.side_effect = [
            _slots(),
            [
                {"category_id": 1, "slug": "region", "keyword_id": 1, "value": "강남구"},
                {"category_id": 1, "slug": "region", "keyword_id": 2, "value": "수원시"},
            ],
        ]
        sel    = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.get_picked_keyword_ids()

        assert result[1] == [1, 2]   # category_id=1 → [강남구_id, 수원시_id]

    def test_unpicked_category_returns_none(self):
        """picks 가 없는 카테고리는 None 을 반환한다 (ComboGenerator 가 전체를 사용)."""
        db = MagicMock()
        db.fetch_all.side_effect = [_slots(), []]
        sel    = CampaignKeywordPicker(db=db, campaign_id=1)
        result = sel.get_picked_keyword_ids()

        assert all(v is None for v in result.values())
