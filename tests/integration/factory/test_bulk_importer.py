"""
tests/integration/factory/test_bulk_importer.py
-------------------------------------------------
BulkImporter integration tests — full DB flow.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from factory.bulk_importer import BulkImporter, PoolImportResult, ResetResult
from factory.models import (
    Account, Batch, BatchItem,
    Campaign, CampaignPalette, CampaignSlot, Combination, Keyword,
    KeywordCategory, PaletteItem, TemplateToken, CampaignKeywordPick,
    SpacingRule,
)
from tests.integration.factory.conftest import make_campaign


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_campaign(session: Session) -> Campaign:
    return make_campaign(
        session, with_categories=False, with_slots=False, with_keywords=False,
    )


# ---------------------------------------------------------------------------
# import_keywords
# ---------------------------------------------------------------------------

class TestImportKeywords:

    def test_creates_categories_and_keywords(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학"],
        })

        assert result.categories_created == 2
        assert result.keywords_created == 3

        cats = session.scalars(select(KeywordCategory)).all()
        cat_slugs = {c.slug for c in cats}
        assert "region" in cat_slugs
        assert "subject" in cat_slugs

    def test_creates_tokens_and_slots(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
        ).all()
        assert len(tokens) == 2
        slugs = {t.slug for t in tokens}
        assert slugs == {"region", "subject"}
        assert all(t.token_type == "keyword" for t in tokens)

        slots = session.scalars(select(CampaignSlot)).all()
        assert len(slots) == 2

    def test_sets_picks(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_keywords({"region": ["수리동", "산본동"]})

        picks = session.scalars(
            select(CampaignKeywordPick)
            .where(CampaignKeywordPick.campaign_id == campaign.id)
        ).all()
        assert len(picks) == 2
        assert result.picks_set == 2

    def test_existing_category_reused(self, session):
        campaign = _bare_campaign(session)

        session.add(KeywordCategory(name="지역", slug="region"))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_keywords({"region": ["수리동"]})

        assert result.categories_created == 0
        assert result.keywords_created == 1

    def test_existing_keyword_reused(self, session):
        campaign = _bare_campaign(session)

        cat = KeywordCategory(name="지역", slug="region")
        session.add(cat)
        session.flush()
        session.add(Keyword(
            category_id=cat.id, value="수리동",
            display_value="수리동", active=True,
        ))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_keywords({"region": ["수리동", "산본동"]})

        assert result.keywords_created == 1
        assert result.keywords_existing == 1

    def test_existing_token_reused(self, session):
        campaign = _bare_campaign(session)
        cat = KeywordCategory(name="지역", slug="region")
        session.add(cat)
        session.flush()

        token = TemplateToken(
            campaign_id=campaign.id, slug="region",
            token_type="keyword", sort_order=0,
        )
        session.add(token)
        session.flush()
        session.add(CampaignSlot(token_id=token.id, category_id=cat.id))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_keywords({"region": ["수리동"]})

        assert result.tokens_created == 0

    def test_deduplicates_values(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_keywords({"region": ["수리동", "수리동", "수리동"]})

        assert result.keywords_created == 1

    def test_multiple_categories_sort_order(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동"],
            "subject": ["수학"],
            "learning_type": ["과외"],
        })

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
            .order_by(TemplateToken.sort_order)
        ).all()
        slugs = [t.slug for t in tokens]
        assert slugs == ["region", "subject", "learning_type"]


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

class TestGenerate:

    def test_generates_combinations(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학"],
        })
        result = importer.generate()

        combos = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert result.combinations_generated == 2
        assert len(combos) == 2

    def test_generates_with_custom_spacing(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학", "영어"],
        })
        result = importer.generate(spacing_patterns=[
            {"region": 1, "subject": 1},
            {"region": 0, "subject": 1},
        ])

        assert result.combinations_generated == 8  # 2×2×2 spacing rules

    def test_generate_without_import_raises(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.generate()
        assert result.combinations_generated == 0


# ---------------------------------------------------------------------------
# Full pipeline — Eric's scenario
# ---------------------------------------------------------------------------

class TestFullPipeline:

    def test_excel_to_combinations(self, session):
        """Eric gives an Excel dict → combinations are generated."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        excel_data = {
            "region": ["수리동", "산본동", "원주시"],
            "subject": ["수학", "영어"],
            "learning_type": ["과외", "학원"],
        }

        import_result = importer.import_keywords(excel_data)
        assert import_result.keywords_created == 7

        gen_result = importer.generate()
        assert gen_result.combinations_generated == 12  # 3×2×2

    def test_add_keywords_and_regenerate(self, session):
        """Eric adds more regions later — no duplicates."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학"],
        })
        first = importer.generate()
        assert first.combinations_generated == 2

        importer.import_keywords({
            "region": ["수리동", "산본동", "원주시"],
            "subject": ["수학"],
        })
        second = importer.generate()
        assert second.combinations_generated == 1  # only 원주시×수학 is new

        total = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(total) == 3

    def test_reimport_removes_stale_combinations(self, session):
        """Eric removes a region from Excel — stale combos cleaned up."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동", "산본동", "원주시"],
            "subject": ["수학"],
        })
        importer.generate()

        total_before = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(total_before) == 3

        importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학"],
        })
        importer.generate()

        total_after = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(total_after) == 2

    def test_typo_fix_replaces_combination(self, session):
        """Eric fixes typo 수리돈→수리동 — old combo gone, new one created."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리돈"], "subject": ["수학"]})
        importer.generate()

        combos_before = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(combos_before) == 1

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})
        importer.generate()

        combos_after = session.scalars(
            select(Combination)
            .where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(combos_after) == 1

        kw_values = {kw.value for combo in combos_after for kw in combo.keywords}
        assert "수리동" in kw_values
        assert "수리돈" not in kw_values

    def test_keywords_plus_salts(self, session):
        """Eric imports keywords AND wants system salts in title."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({
            "region": ["수리동", "산본동"],
            "subject": ["수학"],
        })

        pool_result = importer.import_pools({
            "salt_prefix": ["검증된", "전문"],
            "salt_suffix": ["강력 추천", "즉시 가능"],
        })
        assert pool_result.pools_created == 2
        assert pool_result.items_created == 4

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
            .order_by(TemplateToken.sort_order)
        ).all()
        slugs = [t.slug for t in tokens]
        assert "region" in slugs
        assert "subject" in slugs
        assert "salt_prefix" in slugs
        assert "salt_suffix" in slugs

        gen_result = importer.generate()
        assert gen_result.combinations_generated == 2  # 2×1


# ---------------------------------------------------------------------------
# import_pools
# ---------------------------------------------------------------------------

class TestImportPools:

    def test_creates_pool_tokens_and_palettes(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_pools({
            "salt_prefix": ["검증된", "전문"],
        })

        assert result.pools_created == 1
        assert result.items_created == 2

        token = session.scalars(
            select(TemplateToken).where(
                TemplateToken.campaign_id == campaign.id,
                TemplateToken.slug == "salt_prefix",
            )
        ).first()
        assert token is not None
        assert token.token_type == "pool"
        assert token.palette is not None
        assert len(token.palette.items) == 2

    def test_multiple_pools(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_pools({
            "salt_prefix": ["검증된"],
            "salt_suffix": ["강력 추천", "즉시 가능"],
            "cta": ["지금 신청"],
        })

        assert result.pools_created == 3
        assert result.items_created == 4

    def test_existing_pool_token_adds_items(self, session):
        """If pool token already exists, new items are appended."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_pools({"salt_prefix": ["검증된"]})
        result = importer.import_pools({"salt_prefix": ["전문", "최고의"]})

        assert result.pools_created == 0
        assert result.items_created == 2

        token = session.scalars(
            select(TemplateToken).where(
                TemplateToken.campaign_id == campaign.id,
                TemplateToken.slug == "salt_prefix",
            )
        ).first()
        assert len(token.palette.items) == 3

    def test_duplicate_items_skipped(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_pools({"salt_prefix": ["검증된", "전문"]})
        result = importer.import_pools({"salt_prefix": ["검증된", "최고의"]})

        assert result.items_created == 1
        assert result.items_existing == 1

    def test_sort_order_after_keywords(self, session):
        """Pool tokens get sort_order after existing keyword tokens."""
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})
        importer.import_pools({"salt_suffix": ["추천"]})

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
            .order_by(TemplateToken.sort_order)
        ).all()
        slugs = [t.slug for t in tokens]
        assert slugs[-1] == "salt_suffix"

    def test_empty_data_raises(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        with pytest.raises(ValueError, match="empty"):
            importer.import_pools({})

    def test_empty_values_raises(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        with pytest.raises(ValueError, match="empty"):
            importer.import_pools({"salt_prefix": []})


# ---------------------------------------------------------------------------
# import_from_excel — header resolution with DB lookup
# ---------------------------------------------------------------------------

class TestImportFromExcel:

    def test_korean_headers_resolved_by_category_name(self, session):
        """Korean header '지역' resolved via KeywordCategory.name → slug 'region'."""
        campaign = _bare_campaign(session)

        session.add(KeywordCategory(name="지역", slug="region"))
        session.add(KeywordCategory(name="과목", slug="subject"))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_from_excel(
            headers=["지역", "과목"],
            rows=[["수리동", "수학"], ["산본동", "영어"]],
        )

        assert result.keywords_created == 4
        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
        ).all()
        slugs = {t.slug for t in tokens}
        assert slugs == {"region", "subject"}

    def test_explicit_header_map_overrides(self, session):
        campaign = _bare_campaign(session)

        session.add(KeywordCategory(name="지역", slug="region"))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_from_excel(
            headers=["지역", "과목"],
            rows=[["수리동", "수학"]],
            header_map={"지역": "area", "과목": "subject"},
        )

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
        ).all()
        slugs = {t.slug for t in tokens}
        assert "area" in slugs
        assert "subject" in slugs

    def test_english_headers_pass_through(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        result = importer.import_from_excel(
            headers=["region", "subject"],
            rows=[["수리동", "수학"]],
        )

        assert result.keywords_created == 2

    def test_mixed_resolved_and_passthrough(self, session):
        campaign = _bare_campaign(session)

        session.add(KeywordCategory(name="지역", slug="region"))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        result = importer.import_from_excel(
            headers=["지역", "subject"],
            rows=[["수리동", "수학"]],
        )

        tokens = session.scalars(
            select(TemplateToken)
            .where(TemplateToken.campaign_id == campaign.id)
        ).all()
        slugs = {t.slug for t in tokens}
        assert slugs == {"region", "subject"}

    def test_unresolvable_header_raises(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        with pytest.raises(ValueError, match="알수없음"):
            importer.import_from_excel(
                headers=["알수없음"],
                rows=[["뭔가"]],
            )

    def test_full_pipeline_korean_excel(self, session):
        """Minji's scenario: Korean Excel → combinations."""
        campaign = _bare_campaign(session)

        session.add(KeywordCategory(name="지역", slug="region"))
        session.add(KeywordCategory(name="과목", slug="subject"))
        session.add(KeywordCategory(name="학습형태", slug="learning_type"))
        session.flush()

        importer = BulkImporter(session, campaign.id)
        importer.import_from_excel(
            headers=["지역", "과목", "학습형태"],
            rows=[
                ["수리동", "수학", "과외"],
                ["산본동", "영어", "학원"],
                ["원주시", "",     ""],
            ],
        )
        gen = importer.generate()
        assert gen.combinations_generated == 12  # 3×2×2


# ---------------------------------------------------------------------------
# soft_reset / hard_reset
# ---------------------------------------------------------------------------

class TestSoftReset:

    def test_deletes_undispatched_combinations(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동", "산본동"], "subject": ["수학"]})
        importer.generate()

        combos_before = session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(combos_before) == 2

        result = importer.soft_reset()
        session.flush()

        combos_after = session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(combos_after) == 0
        assert result.combinations_removed == 2

    def test_preserves_dispatched_combinations(self, session):
        from factory.models import Batch, BatchItem, Account

        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동", "산본동"], "subject": ["수학"]})
        importer.generate()

        combos = session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(combos) == 2

        account = Account(
            user_id=campaign.user_id, platform_id=campaign.platform_id,
            username="test_account",
        )
        session.add(account)
        session.flush()

        from datetime import datetime, timezone
        batch = Batch(
            campaign_id=campaign.id, account_id=account.id,
            scheduled_at=datetime.now(timezone.utc), status="pending",
        )
        session.add(batch)
        session.flush()

        session.add(BatchItem(
            batch_id=batch.id, combination_id=combos[0].id, status="pending",
        ))
        session.flush()

        result = importer.soft_reset()
        session.flush()

        remaining = session.scalars(
            select(Combination).where(Combination.campaign_id == campaign.id)
        ).all()
        assert len(remaining) == 1
        assert remaining[0].id == combos[0].id
        assert result.combinations_removed == 1
        assert result.combinations_preserved == 1

    def test_preserves_tokens_and_picks(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})
        importer.generate()
        importer.soft_reset()

        tokens = session.scalars(
            select(TemplateToken).where(TemplateToken.campaign_id == campaign.id)
        ).all()
        picks = session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == campaign.id
            )
        ).all()
        assert len(tokens) == 2
        assert len(picks) == 2


class TestHardReset:

    def test_deletes_everything_except_dispatched(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})
        importer.import_pools({"salt_suffix": ["추천"]})
        importer.generate()

        result = importer.hard_reset()
        session.flush()

        assert result.combinations_removed >= 0

        tokens = session.scalars(
            select(TemplateToken).where(TemplateToken.campaign_id == campaign.id)
        ).all()
        picks = session.scalars(
            select(CampaignKeywordPick).where(
                CampaignKeywordPick.campaign_id == campaign.id
            )
        ).all()
        rules = session.scalars(
            select(SpacingRule).where(SpacingRule.campaign_id == campaign.id)
        ).all()
        assert len(tokens) == 0
        assert len(picks) == 0
        assert len(rules) == 0

    def test_can_reimport_after_hard_reset(self, session):
        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동"], "subject": ["수학"]})
        importer.generate()

        importer.hard_reset()

        importer.import_keywords({"region": ["원주시"], "subject": ["영어"]})
        gen = importer.generate()
        assert gen.combinations_generated == 1


# ---------------------------------------------------------------------------
# Affix auto-detection on import
# ---------------------------------------------------------------------------

class TestAffixAutoDetect:

    def test_import_keywords_auto_links_affixes(self, session):
        from factory.models import Affix, keyword_affixes

        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords(
            {"region": ["수리동", "산본동", "강남구"]},
            auto_detect_affixes=True,
        )

        dong_affix = session.scalars(
            select(Affix).where(Affix.type == "suffix", Affix.value == "동")
        ).first()
        gu_affix = session.scalars(
            select(Affix).where(Affix.type == "suffix", Affix.value == "구")
        ).first()
        assert dong_affix is not None
        assert gu_affix is not None

        suri = session.scalars(
            select(Keyword).where(Keyword.value == "수리동")
        ).first()
        assert dong_affix in suri.affixes

        gangnam = session.scalars(
            select(Keyword).where(Keyword.value == "강남구")
        ).first()
        assert gu_affix in gangnam.affixes

    def test_no_auto_detect_by_default(self, session):
        from factory.models import Affix

        campaign = _bare_campaign(session)
        importer = BulkImporter(session, campaign.id)

        importer.import_keywords({"region": ["수리동", "산본동"]})

        affixes = session.scalars(select(Affix)).all()
        assert len(affixes) == 0

    def test_existing_affix_reused(self, session):
        from factory.models import Affix

        campaign = _bare_campaign(session)

        existing = Affix(type="suffix", value="동", sort_order=0)
        session.add(existing)
        session.flush()

        importer = BulkImporter(session, campaign.id)
        importer.import_keywords(
            {"region": ["수리동", "산본동"]},
            auto_detect_affixes=True,
        )

        all_dong = session.scalars(
            select(Affix).where(Affix.type == "suffix", Affix.value == "동")
        ).all()
        assert len(all_dong) == 1
