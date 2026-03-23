"""
dev/seed.py
-------------
Seed the database with minimal test data for all 4 steps.

Usage:
    python dev/seed.py          # seed
    python dev/seed.py --clean  # drop + recreate + seed

Requires:
    - .env with DB_* variables
    - MySQL running (bash ./run/factory.sh db-up)
    - Schema created (bash ./run/factory.sh schema-init)

Creates:
    User           1   test@example.com / test1234
    Platform       1   naver
    Account        2   myblog01, myblog02
    KeywordCategory 2  region (3 keywords), subject (2 keywords)
    Affix          2   suffix 동, suffix 시
    keyword_affixes    강남동↔동, 수원시↔시
    PostLayout     1   "Standard SEO" (5 slots)
    PoolToken      2   salt_prefix (3 items), salt_suffix (3 items)
    Campaign       1   "시드 캠페인" (fully wired for Step 3/4 testing)
"""

from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.orm import Session

from factory.db import get_engine, create_schema, drop_schema
from factory.models import (
    Account,
    Affix,
    Campaign,
    CampaignKeywordPick,
    CampaignPalette,
    CampaignSlot,
    Keyword,
    KeywordCategory,
    LayoutSlot,
    PaletteItem,
    Platform,
    PostLayout,
    SpacingRule,
    TemplateToken,
    User,
)


def seed(session: Session) -> None:
    """Insert minimal test data."""

    # ── User ─────────────────────────────────────────────────────────────
    user = User(
        email="test@example.com",
        password_hash=sha256(b"test1234").hexdigest(),
        display_name="Eric",
        role="operator",
    )
    session.add(user)
    session.flush()
    print(f"  User:     {user.email} / test1234 (id={user.id})")

    # ── Platform ─────────────────────────────────────────────────────────
    platform = Platform(
        name="Naver Blog",
        slug="naver",
        base_url="https://blog.naver.com",
    )
    session.add(platform)
    session.flush()
    print(f"  Platform: {platform.name} (id={platform.id})")

    # ── Accounts ─────────────────────────────────────────────────────────
    accounts = []
    for username, blog_id in [("myblog01", "myblog01"), ("myblog02", "myblog02")]:
        acct = Account(
            user_id=user.id,
            platform_id=platform.id,
            username=username,
            password_enc="password123",
            extra={"blog_id": blog_id},
            cooldown_days=14,
            status="active",
        )
        session.add(acct)
        accounts.append(acct)
    session.flush()
    print(f"  Accounts: {len(accounts)} (myblog01, myblog02)")

    # ── Keyword Categories + Keywords ────────────────────────────────────
    cat_region = KeywordCategory(name="지역", slug="region")
    cat_subject = KeywordCategory(name="과목", slug="subject")
    session.add_all([cat_region, cat_subject])
    session.flush()

    region_keywords = []
    for i, val in enumerate(["강남동", "수원시", "판교"]):
        kw = Keyword(
            category_id=cat_region.id,
            value=val,
            display_value="",
            active=True,
            sort_order=i,
        )
        session.add(kw)
        region_keywords.append(kw)

    subject_keywords = []
    for i, val in enumerate(["수학", "영어"]):
        kw = Keyword(
            category_id=cat_subject.id,
            value=val,
            display_value="",
            active=True,
            sort_order=i,
        )
        session.add(kw)
        subject_keywords.append(kw)

    session.flush()
    print(f"  Keywords: region({len(region_keywords)}), subject({len(subject_keywords)})")

    # ── Affixes + keyword_affixes links ──────────────────────────────────
    affix_dong = Affix(type="suffix", value="동", sort_order=0)
    affix_si = Affix(type="suffix", value="시", sort_order=1)
    session.add_all([affix_dong, affix_si])
    session.flush()

    # 강남동 ↔ 동, 수원시 ↔ 시
    region_keywords[0].affixes.append(affix_dong)
    region_keywords[1].affixes.append(affix_si)
    session.flush()
    print(f"  Affixes:  동(→강남동), 시(→수원시)")

    # ── PostLayout + LayoutSlots ─────────────────────────────────────────
    layout = PostLayout(
        user_id=user.id,
        name="Standard SEO Post",
        description="Heading + 3 paragraphs + featured image",
    )
    session.add(layout)
    session.flush()

    slots = [
        ("heading",   0, {"level": 2}),
        ("paragraph", 1, {"tone": "informational", "min_chars": 200}),
        ("paragraph", 2, {}),
        ("paragraph", 3, {}),
        ("featured",  4, {}),
    ]
    for block_type, order, config in slots:
        session.add(LayoutSlot(
            layout_id=layout.id,
            sort_order=order,
            block_type=block_type,
            config=config,
        ))
    session.flush()
    print(f"  Layout:   '{layout.name}' ({len(slots)} blocks)")

    # ── Campaign (fully wired for Step 3/4 testing) ──────────────────────
    campaign = Campaign(
        user_id=user.id,
        platform_id=platform.id,
        layout_id=layout.id,
        name="시드 캠페인",
        description="Seed data for testing",
        status="active",
    )
    session.add(campaign)
    session.flush()

    # Title tokens: {region} {subject} {salt_suffix}
    token_region = TemplateToken(
        campaign_id=campaign.id, slug="region",
        token_type="keyword", sort_order=0,
    )
    token_subject = TemplateToken(
        campaign_id=campaign.id, slug="subject",
        token_type="keyword", sort_order=1,
    )
    token_salt_suffix = TemplateToken(
        campaign_id=campaign.id, slug="salt_suffix",
        token_type="pool", sort_order=2,
    )
    session.add_all([token_region, token_subject, token_salt_suffix])
    session.flush()

    # Campaign slots (keyword token → category binding)
    session.add(CampaignSlot(token_id=token_region.id, category_id=cat_region.id))
    session.add(CampaignSlot(token_id=token_subject.id, category_id=cat_subject.id))
    session.flush()

    # Pool: salt_suffix
    palette = CampaignPalette(
        token_id=token_salt_suffix.id,
        strategy="random",
    )
    session.add(palette)
    session.flush()

    for i, val in enumerate(["추천", "강력 추천", "즉시 가능"]):
        session.add(PaletteItem(
            palette_id=palette.token_id,
            value=val,
            sort_order=i,
            active=True,
        ))

    # Pool: salt_prefix (standalone, not in this campaign's template)
    token_salt_prefix = TemplateToken(
        campaign_id=campaign.id, slug="salt_prefix",
        token_type="pool", sort_order=99,
    )
    session.add(token_salt_prefix)
    session.flush()

    palette_prefix = CampaignPalette(
        token_id=token_salt_prefix.id,
        strategy="random",
    )
    session.add(palette_prefix)
    session.flush()

    for i, val in enumerate(["검증된", "전문", "인기"]):
        session.add(PaletteItem(
            palette_id=palette_prefix.token_id,
            value=val,
            sort_order=i,
            active=True,
        ))
    session.flush()
    print(f"  Pools:    salt_suffix(3), salt_prefix(3)")

    # Keyword picks (all active keywords → campaign)
    for kw in region_keywords + subject_keywords:
        session.add(CampaignKeywordPick(
            campaign_id=campaign.id,
            category_id=kw.category_id,
            keyword_id=kw.id,
        ))
    session.flush()

    # Spacing rules (2 styles)
    session.add(SpacingRule(
        campaign_id=campaign.id,
        pattern={"region": 1, "subject": 1, "salt_suffix": 1},
        description="Normal",
        active=True,
    ))
    session.add(SpacingRule(
        campaign_id=campaign.id,
        pattern={"region": 0, "subject": 1, "salt_suffix": 1},
        description="Compact",
        active=True,
    ))
    session.flush()
    print(f"  Spacing:  2 styles (Normal, Compact)")

    print(f"  Campaign: '{campaign.name}' (id={campaign.id})")

    session.commit()
    print()
    print("  ✅ Seed complete.")


def main():
    engine = get_engine()

    if "--clean" in sys.argv:
        print("  Dropping all tables...")
        drop_schema(engine)
        print("  Creating all tables...")
        create_schema(engine)
        print()

    print("  ── Seeding ──────────────────────────")
    with Session(engine) as session:
        seed(session)

    print()
    print("  Login:  POST /api/spa/v1/auth/login")
    print("          email: test@example.com")
    print("          password: test1234")
    print()
    print("  IDs:    campaign=1, layout=1, platform=1")
    print()


if __name__ == "__main__":
    main()
