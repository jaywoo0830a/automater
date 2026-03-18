"""
factory/tests/test_campaign_slots.py
--------------------------------------
ComboGenerator 단위 테스트.
build_combos() 는 순수 함수이므로 DB 없이 검증한다.
ComboGenerator.run() 은 SQLAlchemy 2.0 select() 스타일로 DB 상태를 검증한다.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.combo_generator import ComboGenerator, build_combos
from factory.models import Combination, Keyword, SpacingRule
from factory.tests.conftest import make_campaign


# ---------------------------------------------------------------------------
# build_combos() — 순수 함수, DB 불필요
# ---------------------------------------------------------------------------

class TestBuildCombos:

    def test_total_count(self):
        """2×2×2 × 3 spacing × 2 has_suffix = 48"""
        assert len(build_combos([[1, 2], [3, 4], [5, 6]], [10, 20, 30], [0, 1])) == 48

    def test_required_keys(self):
        for combo in build_combos([[1], [2]], [10], [0]):
            assert {"keyword_ids", "spacing_rule_id", "has_suffix"} <= combo.keys()

    def test_no_duplicates(self):
        combos = build_combos([[1, 2], [3, 4]], [10, 20], [0, 1])
        keys   = [(tuple(c["keyword_ids"]), c["spacing_rule_id"], c["has_suffix"]) for c in combos]
        assert len(keys) == len(set(keys))

    def test_empty_keyword_group_returns_empty(self):
        assert build_combos([[], [1]], [10], [0]) == []

    def test_empty_spacing_rules_returns_empty(self):
        assert build_combos([[1], [2]], [], [0]) == []


# ---------------------------------------------------------------------------
# ComboGenerator.run() — 실제 DB
# ---------------------------------------------------------------------------

class TestComboGeneratorRun:

    def test_inserted_count_matches_cartesian_product(self, session: Session):
        """region(2) × subject(2) × lt(2) × spacing(1) × has_suffix(2) = 16"""
        campaign = make_campaign(session)
        inserted = ComboGenerator(session=session, campaign_id=campaign.id).run()
        session.flush()
        assert inserted == 16

    def test_each_combination_has_correct_keyword_count(self, session: Session):
        campaign = make_campaign(session)
        ComboGenerator(session=session, campaign_id=campaign.id).run()
        session.flush()

        for combo in session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all():
            assert len(combo.keywords) == 3

    def test_config_stores_has_suffix(self, session: Session):
        campaign = make_campaign(session)
        ComboGenerator(session=session, campaign_id=campaign.id).run()
        session.flush()

        for combo in session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all():
            assert "has_suffix" in (combo.config or {})

    def test_no_slots_returns_zero(self, session: Session):
        campaign = make_campaign(session, with_slots=False, with_keywords=False)
        assert ComboGenerator(session=session, campaign_id=campaign.id).run() == 0

    def test_inactive_spacing_rule_returns_zero(self, session: Session):
        campaign = make_campaign(session)
        session.execute(
            SpacingRule.__table__.update()
            .where(SpacingRule.campaign_id == campaign.id)
            .values(active=False)
        )
        session.flush()
        assert ComboGenerator(session=session, campaign_id=campaign.id).run() == 0

    def test_inactive_keyword_excluded(self, session: Session):
        """active=False 인 성남시는 조합에 포함되지 않는다."""
        campaign = make_campaign(session)
        ComboGenerator(session=session, campaign_id=campaign.id).run()
        session.flush()

        inactive = session.scalars(
            select(Keyword).where(Keyword.value == "성남시")
        ).first()
        assert inactive is not None

        combos_with_inactive = session.scalars(
            select(Combination).where(
                Combination.campaign_id == campaign.id,
                Combination.keywords.any(Keyword.id == inactive.id),
            )
        ).all()
        assert combos_with_inactive == []

    def test_picks_filter_reduces_count(self, session: Session):
        """region 을 강남구 하나로 제한하면 절반으로 줄어든다."""
        from factory.keyword_picker import CampaignKeywordPicker

        campaign = make_campaign(session)
        picker   = CampaignKeywordPicker(session=session, campaign_id=campaign.id)
        picker.pick(category_slug="region", values=["강남구"])
        session.flush()
        picks = picker.get_picked_keyword_ids()

        inserted = ComboGenerator(session=session, campaign_id=campaign.id, picks=picks).run()
        session.flush()

        # region 1 × subject 2 × lt 2 × spacing 1 × has_suffix 2 = 8
        assert inserted == 8
