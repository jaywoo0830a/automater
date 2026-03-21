"""
tests/integration/factory/test_keyword_picker.py
--------------------------------------
CampaignKeywordPicker 단위 테스트.
SQLAlchemy 2.0 select() 스타일로 DB 상태를 검증한다.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.keyword_picker import CampaignKeywordPicker
from factory.models import CampaignKeywordPick, Keyword
from tests.integration.factory.conftest import make_campaign


class TestSavePicks:

    def test_inserts_correct_keyword_ids(self, session: Session):
        """선택한 value 에 해당하는 keyword_id 만 DB 에 저장된다."""
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        count    = picker.save_picks(category_slug="region", values=["강남구", "수원시"])
        session.flush()

        picks = session.scalars(
            select(CampaignKeywordPick).where(CampaignKeywordPick.campaign_id == campaign.id)
        ).all()
        expected_ids = {
            kw.id for kw in session.scalars(
                select(Keyword).where(Keyword.value.in_(["강남구", "수원시"]))
            ).all()
        }

        assert {p.keyword_id for p in picks} == expected_ids
        assert count == 2

    def test_overwrites_existing_picks(self, session: Session):
        """같은 카테고리에 두 번 pick 하면 이전 선택이 완전히 교체된다."""
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)

        picker.save_picks(category_slug="region", values=["강남구"])
        session.flush()
        picker.save_picks(category_slug="region", values=["수원시"])
        session.flush()

        values_in_db = {
            p.keyword.value for p in session.scalars(
                select(CampaignKeywordPick).where(CampaignKeywordPick.campaign_id == campaign.id)
            ).all()
        }
        assert values_in_db == {"수원시"}

    def test_empty_values_clears_picks(self, session: Session):
        """빈 리스트를 전달하면 해당 카테고리의 picks 가 제거된다."""
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)

        picker.save_picks(category_slug="region", values=["강남구"])
        session.flush()
        picker.save_picks(category_slug="region", values=[])
        session.flush()

        picks = session.scalars(
            select(CampaignKeywordPick).where(CampaignKeywordPick.campaign_id == campaign.id)
        ).all()
        assert picks == []

    def test_unknown_keyword_raises(self, session: Session):
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        with pytest.raises(ValueError, match="없는 키워드"):
            picker.save_picks(category_slug="region", values=["없는동네"])

    def test_unknown_category_raises(self, session: Session):
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        with pytest.raises(ValueError, match="category"):
            picker.save_picks(category_slug="nonexistent", values=["강남구"])

    def test_inactive_keyword_raises(self, session: Session):
        """active=False 인 키워드(성남시)는 선택할 수 없다."""
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        with pytest.raises(ValueError, match="없는 키워드"):
            picker.save_picks(category_slug="region", values=["성남시"])


class TestLoadPicks:

    def test_returns_per_category_dict(self, session: Session):
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)

        picker.save_picks(category_slug="region",  values=["강남구", "수원시"])
        picker.save_picks(category_slug="subject", values=["수학"])
        session.flush()

        result = picker.load_picks()
        assert set(result["region"])   == {"강남구", "수원시"}
        assert result["subject"]       == ["수학"]
        assert result["learning_type"] == []

    def test_no_picks_returns_empty_lists(self, session: Session):
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        assert all(v == [] for v in picker.load_picks().values())


class TestLoadPickIds:

    def test_picked_returns_id_list_unpicked_returns_none(self, session: Session):
        campaign = make_campaign(session, with_picks=False)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)

        picker.save_picks(category_slug="region", values=["강남구"])
        session.flush()

        result      = picker.load_pick_ids()
        empty_count = sum(1 for v in result.values() if v == [])
        filled_count = sum(1 for v in result.values() if len(v) > 0)

        assert empty_count == 2   # subject, learning_type
        assert filled_count == 1   # region
