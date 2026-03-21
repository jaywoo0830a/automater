"""
tests/integration/factory/conftest.py
--------------------------
SQLAlchemy 2.0 공식 패턴 기반 테스트 픽스처.

참고: https://docs.sqlalchemy.org/en/20/orm/session_basics.html

격리 전략
----------
앱 코드(keyword_picker / combo_generator / dispatcher)는
session.commit() 을 직접 호출하지 않는다.
add() / flush() 만 사용하므로 SQLAlchemy의 autobegin 트랜잭션 안에
모든 변경이 쌓인다.

teardown 에서 session.rollback() 을 호출하면
flush() 로 쓴 내용이 전부 취소되어 다음 테스트가 깨끗한 DB 에서 시작한다.
"""

from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from factory.db import create_schema, drop_schema
from factory.models import (
    Base, User, Platform, Campaign, KeywordCategory,
    Keyword, TemplateToken, CampaignSlot, CampaignKeywordPick, SpacingRule,
    Affix, CampaignAffixOverride, CampaignPalette, PaletteItem,
)


# ---------------------------------------------------------------------------
# Engine — 테스트 세션 전체에서 한 번만 생성
# ---------------------------------------------------------------------------

def _test_url() -> str:
    url = os.environ.get("TEST_DB_URL")
    if not url:
        raise RuntimeError(
            "TEST_DB_URL 환경변수가 없습니다.\n"
            "  bash ./run/test.sh --factory  로 실행하세요."
        )
    return url


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(_test_url())
    create_schema(eng)
    yield eng
    drop_schema(eng)
    eng.dispose()


# ---------------------------------------------------------------------------
# Session — 공식 패턴: Session(engine) + rollback()
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def session(engine) -> Session:
    """
    SQLAlchemy 2.0 공식 패턴.

    Session(engine) 으로 세션을 열면 첫 SQL 에서 autobegin 이 발동해
    트랜잭션이 시작된다. 테스트 종료 시 rollback() 으로 모든 변경을 취소한다.

    공식 문서:
        with Session(engine) as session:
            session.add(obj)
            session.commit()  # 운영 코드는 commit

    테스트에서는 commit 대신 rollback 으로 격리한다.
    """
    with Session(engine) as sess:
        yield sess
        sess.rollback()


# ---------------------------------------------------------------------------
# 표준 테스트 데이터 빌더
# ---------------------------------------------------------------------------

def make_campaign(
    session: Session,
    *,
    with_categories: bool = True,
    with_slots:      bool = True,
    with_keywords:   bool = True,
    with_picks:      bool = True,
) -> Campaign:
    """
    최소한의 완전한 캠페인 픽스처를 삽입한다.

        Platform 1개
        Campaign 1개
        KeywordCategory 3개 (with_categories=True): region / subject / learning_type
        Keywords (with_keywords=True):
            region:        강남구(active), 수원시(active), 성남시(inactive)
            subject:       수학, 영어
            learning_type: 과외, 학원
        CampaignSlots (with_slots=True) — requires with_categories
        CampaignKeywordPicks (with_picks=True): all active keywords
        SpacingRule 1개 (active)
    """
    platform = Platform(
        name="Naver Blog", slug="naver_blog", base_url="https://blog.naver.com"
    )
    session.add(platform)
    session.flush()

    user = User(
        email="test@example.com",
        password_hash="$argon2id$test_hash",
        display_name="Test User",
        role="operator",
    )
    session.add(user)
    session.flush()

    campaign = Campaign(
        user_id        = user.id,
        platform_id    = platform.id,
        name           = "Test Campaign",
        status         = "active",
    )
    session.add(campaign)
    session.flush()

    if not with_categories:
        return campaign

    region_cat  = KeywordCategory(name="지역",     slug="region")
    subject_cat = KeywordCategory(name="과목",     slug="subject")
    lt_cat      = KeywordCategory(name="학습형태", slug="learning_type")
    session.add_all([region_cat, subject_cat, lt_cat])
    session.flush()

    if with_slots:
        # Keyword tokens — one per category
        token_region = TemplateToken(
            campaign_id=campaign.id, slug="region",
            token_type="keyword", sort_order=0,
        )
        token_subject = TemplateToken(
            campaign_id=campaign.id, slug="subject",
            token_type="keyword", sort_order=1,
        )
        token_lt = TemplateToken(
            campaign_id=campaign.id, slug="learning_type",
            token_type="keyword", sort_order=2,
        )
        session.add_all([token_region, token_subject, token_lt])
        session.flush()

        session.add_all([
            CampaignSlot(token_id=token_region.id,  category_id=region_cat.id),
            CampaignSlot(token_id=token_subject.id, category_id=subject_cat.id),
            CampaignSlot(token_id=token_lt.id,      category_id=lt_cat.id),
        ])
        session.flush()

    if with_keywords:
        session.add_all([
            Keyword(category_id=region_cat.id,  value="강남구", display_value="강남", active=True,  sort_order=1),
            Keyword(category_id=region_cat.id,  value="수원시", display_value="수원", active=True,  sort_order=2),
            Keyword(category_id=region_cat.id,  value="성남시", display_value="성남", active=False, sort_order=3),
            Keyword(category_id=subject_cat.id, value="수학",   display_value="수학", active=True,  sort_order=1),
            Keyword(category_id=subject_cat.id, value="영어",   display_value="영어", active=True,  sort_order=2),
            Keyword(category_id=lt_cat.id,      value="과외",   display_value="과외", active=True,  sort_order=1),
            Keyword(category_id=lt_cat.id,      value="학원",   display_value="학원", active=True,  sort_order=2),
        ])
        session.flush()

        session.add(SpacingRule(
            campaign_id = campaign.id,
            pattern     = {"region": 1, "subject": 1, "learning_type": 0},
            description = "test rule",
            active      = True,
        ))
        session.flush()

        # Picks — explicitly bind active keywords to campaign
        if with_picks:
            active_keywords = session.scalars(
                select(Keyword).where(Keyword.active == True)  # noqa: E712
            ).all()
            for kw in active_keywords:
                session.add(CampaignKeywordPick(
                    campaign_id=campaign.id,
                    category_id=kw.category_id,
                    keyword_id=kw.id,
                ))
            session.flush()

        # Affix examples — global affix dictionary + keyword links
        affix_gu = Affix(type="suffix", value="구", sort_order=0)
        affix_dong_suffix = Affix(type="suffix", value="동", sort_order=1)
        affix_dong_prefix = Affix(type="prefix", value="동", sort_order=0)
        session.add_all([affix_gu, affix_dong_suffix, affix_dong_prefix])
        session.flush()

        gangnam = session.scalars(
            select(Keyword).where(Keyword.value == "강남구")
        ).first()
        if gangnam:
            gangnam.affixes = [affix_gu, affix_dong_suffix, affix_dong_prefix]
            session.flush()

        # Palette tokens — runtime sampling pools
        token_salt_prefix = TemplateToken(
            campaign_id=campaign.id, slug="salt_prefix",
            token_type="pool", sort_order=10,
        )
        token_salt_suffix = TemplateToken(
            campaign_id=campaign.id, slug="salt_suffix",
            token_type="pool", sort_order=11,
        )
        session.add_all([token_salt_prefix, token_salt_suffix])
        session.flush()

        palette_prefix = CampaignPalette(
            token_id=token_salt_prefix.id, strategy="random",
        )
        palette_suffix = CampaignPalette(
            token_id=token_salt_suffix.id, strategy="random",
        )
        session.add_all([palette_prefix, palette_suffix])
        session.flush()

        session.add_all([
            PaletteItem(palette_id=palette_prefix.token_id, value="검증된",   sort_order=0),
            PaletteItem(palette_id=palette_prefix.token_id, value="전문",     sort_order=1),
            PaletteItem(palette_id=palette_suffix.token_id, value="강력 추천", sort_order=0),
            PaletteItem(palette_id=palette_suffix.token_id, value="즉시 가능", sort_order=1),
        ])
        session.flush()

    return campaign
