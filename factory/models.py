"""
factory/models.py
------------------
SQLAlchemy 2.0 ORM models — single source of truth for schema.

Use db.create_schema(engine) to create tables from these models.

Table map:
    User                  → users                  (SPA login, owns accounts/campaigns)
    Platform              → platforms
    Account               → accounts               (user_id FK)
    Media                 → media                   (user-uploaded files)
    KeywordCategory       → keyword_categories
    Keyword               → keywords
    Affix                 → affixes                (global affix dictionary)
    keyword_affixes       → keyword_affixes        (keyword ↔ affix M2M)
    CampaignAffixOverride → campaign_affix_overrides (per-campaign keyword-affix toggle)
    Campaign              → campaigns              (user_id FK, 3 nullable preset FKs)
    CampaignSlot          → campaign_slots
    TemplateToken         → template_tokens        (unified slug namespace per campaign)
    SpacingRule           → spacing_rules
    CampaignKeywordPick   → campaign_keyword_picks
    CampaignPalette       → campaign_palettes      (pool config for a token)
    PaletteItem           → palette_items           (individual pool values)
    PostLayout            → post_layouts            (reusable block sequence)
    LayoutSlot            → layout_slots            (block_type + config JSON)
    PublishPreset         → publish_presets          (PublishOption as JSON config)
    RunPreset             → run_presets              (RunSetting as JSON config)
    combination_keywords  → combination_keywords    (association table)
    Combination           → combinations
    Batch                 → batches
    BatchItem             → batch_items
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
)

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Association table — combination_keywords (no extra columns)
# ---------------------------------------------------------------------------

combination_keywords = Table(
    "combination_keywords",
    Base.metadata,
    Column(
        "combination_id",
        BigInteger,
        ForeignKey("combinations.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "keyword_id",
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


# ---------------------------------------------------------------------------
# Association table — keyword_affixes (keyword <-> affix many-to-many)
# ---------------------------------------------------------------------------

keyword_affixes = Table(
    "keyword_affixes",
    Base.metadata,
    Column(
        "keyword_id",
        Integer,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
    Column(
        "affix_id",
        Integer,
        ForeignKey("affixes.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    ),
)


# ---------------------------------------------------------------------------
# User — SPA login account (owns Accounts and Campaigns)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id:            Mapped[int]                = mapped_column(Integer,     primary_key=True, autoincrement=True)
    email:         Mapped[str]                = mapped_column(String(256), nullable=False, unique=True)
    password_hash: Mapped[str]                = mapped_column(String(512), nullable=False)
    display_name:  Mapped[str]                = mapped_column(String(64),  nullable=False, default="")
    role:          Mapped[str]                = mapped_column(String(16),  nullable=False, default="operator")
    status:        Mapped[str]                = mapped_column(String(16),  nullable=False, default="active")
    created_at:    Mapped[datetime]           = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime,    nullable=True)

    # relationships
    accounts:        Mapped[list["Account"]]        = relationship("Account",       back_populates="owner")
    campaigns:       Mapped[list["Campaign"]]       = relationship("Campaign",      back_populates="owner")
    layouts:         Mapped[list["PostLayout"]]      = relationship("PostLayout",    back_populates="owner")
    publish_presets: Mapped[list["PublishPreset"]]   = relationship("PublishPreset", back_populates="owner")
    run_presets:     Mapped[list["RunPreset"]]       = relationship("RunPreset",     back_populates="owner")
    media:           Mapped[list["Media"]]           = relationship("Media",         back_populates="owner")


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

class Platform(Base):
    __tablename__ = "platforms"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:       Mapped[str]           = mapped_column(String(64),  nullable=False)
    slug:       Mapped[str]           = mapped_column(String(32),  nullable=False, unique=True)
    base_url:   Mapped[str]           = mapped_column(String(256), nullable=False, default="")
    status:     Mapped[str]           = mapped_column(String(16),  nullable=False, default="active")
    created_at: Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    accounts:  Mapped[list["Account"]]  = relationship("Account",  back_populates="platform")
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="platform")


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("platform_id", "username", name="uq_platform_user"),
    )

    id:            Mapped[int]           = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:       Mapped[int]           = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    platform_id:   Mapped[int]           = mapped_column(Integer,     ForeignKey("platforms.id"), nullable=False)
    username:      Mapped[str]           = mapped_column(String(128), nullable=False)
    password_enc:  Mapped[str]           = mapped_column(String(512), nullable=False, default="")
    extra:         Mapped[dict[str, Any] | None]= mapped_column(JSON,        nullable=True)
    last_used_at:  Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cooldown_days: Mapped[int]           = mapped_column(Integer,     nullable=False, default=14)
    status:        Mapped[str]           = mapped_column(String(16),  nullable=False, default="active")
    note:          Mapped[str]           = mapped_column(String(256), nullable=False, default="")
    created_at:    Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner:    Mapped["User"]          = relationship("User",     back_populates="accounts")
    platform: Mapped["Platform"]      = relationship("Platform", back_populates="accounts")
    batches:  Mapped[list["Batch"]]   = relationship("Batch",    back_populates="account")


# ---------------------------------------------------------------------------
# Media — user-uploaded files (images, thumbnails)
# ---------------------------------------------------------------------------

class Media(Base):
    __tablename__ = "media"

    id:            Mapped[int]      = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:       Mapped[int]      = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    original_name: Mapped[str]      = mapped_column(String(256), nullable=False)
    content_type:  Mapped[str]      = mapped_column(String(64),  nullable=False)
    storage_path:  Mapped[str]      = mapped_column(String(512), nullable=False, unique=True)
    size_bytes:    Mapped[int]      = mapped_column(Integer,     nullable=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner: Mapped["User"] = relationship("User", back_populates="media")


# ---------------------------------------------------------------------------
# KeywordCategory
# ---------------------------------------------------------------------------

class KeywordCategory(Base):
    __tablename__ = "keyword_categories"

    id:         Mapped[int]      = mapped_column(Integer,    primary_key=True, autoincrement=True)
    name:       Mapped[str]      = mapped_column(String(64), nullable=False, unique=True)
    slug:       Mapped[str]      = mapped_column(String(32), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    keywords: Mapped[list["Keyword"]]      = relationship("Keyword",      back_populates="category")
    slots:    Mapped[list["CampaignSlot"]] = relationship("CampaignSlot", back_populates="category")
    picks:    Mapped[list["CampaignKeywordPick"]] = relationship(
        "CampaignKeywordPick", back_populates="category"
    )


# ---------------------------------------------------------------------------
# Keyword
# ---------------------------------------------------------------------------

class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (
        UniqueConstraint("category_id", "value", name="uq_cat_value"),
    )

    id:            Mapped[int]           = mapped_column(Integer,      primary_key=True, autoincrement=True)
    category_id:   Mapped[int]           = mapped_column(Integer,      ForeignKey("keyword_categories.id"), nullable=False)
    parent_id:     Mapped[Optional[int]] = mapped_column(Integer,      ForeignKey("keywords.id"), nullable=True)
    value:         Mapped[str]           = mapped_column(String(128),  nullable=False)
    display_value: Mapped[str]           = mapped_column(String(128),  nullable=False, default="")
    tier:          Mapped[int]           = mapped_column(Integer,      nullable=False, default=1)
    active:        Mapped[bool]          = mapped_column(Boolean,      nullable=False, default=True)
    sort_order:    Mapped[int]           = mapped_column(Integer,      nullable=False, default=0)
    metadata_:     Mapped[dict[str, Any] | None]= mapped_column("metadata",   JSON, nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime,     nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    category: Mapped["KeywordCategory"]     = relationship("KeywordCategory", back_populates="keywords")
    parent:   Mapped[Optional["Keyword"]]   = relationship(
        "Keyword", remote_side="Keyword.id", back_populates="children"
    )
    children: Mapped[list["Keyword"]]       = relationship("Keyword", back_populates="parent")
    combinations: Mapped[list["Combination"]] = relationship(
        "Combination", secondary=combination_keywords, back_populates="keywords"
    )
    picks: Mapped[list["CampaignKeywordPick"]] = relationship(
        "CampaignKeywordPick", back_populates="keyword"
    )
    affixes: Mapped[list["Affix"]] = relationship(
        "Affix", secondary=keyword_affixes, back_populates="keywords",
        order_by="Affix.sort_order",
    )


# ---------------------------------------------------------------------------
# PostLayout — reusable block sequence template
# ---------------------------------------------------------------------------

class PostLayout(Base):
    __tablename__ = "post_layouts"

    id:          Mapped[int]           = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:     Mapped[int]           = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    name:        Mapped[str]           = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    created_at:  Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner: Mapped["User"]              = relationship("User",       back_populates="layouts")
    slots: Mapped[list["LayoutSlot"]]  = relationship(
        "LayoutSlot", back_populates="layout",
        order_by="LayoutSlot.sort_order", cascade="all, delete-orphan",
    )
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="layout")


# ---------------------------------------------------------------------------
# LayoutSlot — one block in a PostLayout
# ---------------------------------------------------------------------------

class LayoutSlot(Base):
    __tablename__ = "layout_slots"

    id:         Mapped[int]      = mapped_column(Integer,    primary_key=True, autoincrement=True)
    layout_id:  Mapped[int]      = mapped_column(Integer,    ForeignKey("post_layouts.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int]      = mapped_column(Integer,    nullable=False, default=0)
    block_type: Mapped[str]      = mapped_column(String(32), nullable=False)
    config:     Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    layout: Mapped["PostLayout"] = relationship("PostLayout", back_populates="slots")


# ---------------------------------------------------------------------------
# PublishPreset — PublishOption content as JSON config
# ---------------------------------------------------------------------------

class PublishPreset(Base):
    __tablename__ = "publish_presets"

    id:          Mapped[int]           = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:     Mapped[int]           = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    name:        Mapped[str]           = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    config:      Mapped[dict[str, Any]]= mapped_column(JSON,        nullable=False)
    created_at:  Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner:     Mapped["User"]              = relationship("User",     back_populates="publish_presets")
    campaigns: Mapped[list["Campaign"]]    = relationship("Campaign", back_populates="publish_preset")


# ---------------------------------------------------------------------------
# RunPreset — RunSetting content as JSON config
# ---------------------------------------------------------------------------

class RunPreset(Base):
    __tablename__ = "run_presets"

    id:          Mapped[int]           = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:     Mapped[int]           = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    name:        Mapped[str]           = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    config:      Mapped[dict[str, Any]]= mapped_column(JSON,        nullable=False)
    created_at:  Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner:     Mapped["User"]              = relationship("User",     back_populates="run_presets")
    campaigns: Mapped[list["Campaign"]]    = relationship("Campaign", back_populates="run_preset")


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

class Campaign(Base):
    __tablename__ = "campaigns"

    id:                 Mapped[int]           = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:            Mapped[int]           = mapped_column(Integer,     ForeignKey("users.id"), nullable=False)
    platform_id:        Mapped[int]           = mapped_column(Integer,     ForeignKey("platforms.id"), nullable=False)
    layout_id:          Mapped[Optional[int]] = mapped_column(Integer,     ForeignKey("post_layouts.id"), nullable=True)
    publish_preset_id:  Mapped[Optional[int]] = mapped_column(Integer,     ForeignKey("publish_presets.id"), nullable=True)
    run_preset_id:      Mapped[Optional[int]] = mapped_column(Integer,     ForeignKey("run_presets.id"), nullable=True)
    name:               Mapped[str]           = mapped_column(String(128), nullable=False)
    description:        Mapped[Optional[str]] = mapped_column(Text,        nullable=True)
    config:             Mapped[dict[str, Any] | None]= mapped_column(JSON, nullable=True)
    status:             Mapped[str]           = mapped_column(String(16),  nullable=False, default="active")
    created_at:         Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    owner:          Mapped["User"]                       = relationship("User",         back_populates="campaigns")
    platform:       Mapped["Platform"]                   = relationship("Platform",     back_populates="campaigns")
    layout:         Mapped[Optional["PostLayout"]]       = relationship("PostLayout",   back_populates="campaigns")
    publish_preset: Mapped[Optional["PublishPreset"]]    = relationship("PublishPreset", back_populates="campaigns")
    run_preset:     Mapped[Optional["RunPreset"]]        = relationship("RunPreset",    back_populates="campaigns")
    tokens:         Mapped[list["TemplateToken"]]        = relationship(
        "TemplateToken", back_populates="campaign",
        order_by="TemplateToken.sort_order", cascade="all, delete-orphan",
    )
    spacing_rules:  Mapped[list["SpacingRule"]]          = relationship("SpacingRule",   back_populates="campaign")
    combinations:   Mapped[list["Combination"]]          = relationship("Combination",   back_populates="campaign")
    batches:        Mapped[list["Batch"]]                = relationship("Batch",         back_populates="campaign")
    picks:          Mapped[list["CampaignKeywordPick"]]  = relationship(
        "CampaignKeywordPick", back_populates="campaign"
    )
    affix_overrides: Mapped[list["CampaignAffixOverride"]] = relationship(
        "CampaignAffixOverride", back_populates="campaign",
    )


# ---------------------------------------------------------------------------
# TemplateToken — unified slug namespace per campaign
# ---------------------------------------------------------------------------

class TemplateToken(Base):
    __tablename__ = "template_tokens"
    __table_args__ = (
        UniqueConstraint("campaign_id", "slug", name="uq_campaign_token_slug"),
    )

    id:          Mapped[int]           = mapped_column(Integer,    primary_key=True, autoincrement=True)
    campaign_id: Mapped[int]           = mapped_column(Integer,    ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    slug:        Mapped[str]           = mapped_column(String(64), nullable=False)
    token_type:  Mapped[str]           = mapped_column(String(16), nullable=False)  # "keyword" | "pool" | "literal"
    value:       Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # text for literal tokens
    sort_order:  Mapped[int]           = mapped_column(Integer,    nullable=False, default=0)
    created_at:  Mapped[datetime]      = mapped_column(DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    campaign: Mapped["Campaign"]                  = relationship("Campaign",        back_populates="tokens")
    slot:     Mapped[Optional["CampaignSlot"]]    = relationship(
        "CampaignSlot", back_populates="token", uselist=False, cascade="all, delete-orphan",
    )
    palette:  Mapped[Optional["CampaignPalette"]] = relationship(
        "CampaignPalette", back_populates="token", uselist=False, cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# CampaignSlot — keyword category binding for a token
# ---------------------------------------------------------------------------

class CampaignSlot(Base):
    __tablename__ = "campaign_slots"

    token_id:    Mapped[int] = mapped_column(Integer, ForeignKey("template_tokens.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("keyword_categories.id"), nullable=False)

    # relationships
    token:    Mapped["TemplateToken"]    = relationship("TemplateToken",    back_populates="slot")
    category: Mapped["KeywordCategory"]  = relationship("KeywordCategory",  back_populates="slots")


# ---------------------------------------------------------------------------
# SpacingRule
# ---------------------------------------------------------------------------

class SpacingRule(Base):
    __tablename__ = "spacing_rules"

    id:          Mapped[int]      = mapped_column(Integer,     primary_key=True, autoincrement=True)
    campaign_id: Mapped[int]      = mapped_column(Integer,     ForeignKey("campaigns.id"), nullable=False)
    pattern:     Mapped[dict[str, Any]]     = mapped_column(JSON,        nullable=False)
    description: Mapped[str]      = mapped_column(String(128), nullable=False, default="")
    active:      Mapped[bool]     = mapped_column(Boolean,     nullable=False, default=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    campaign:     Mapped["Campaign"]         = relationship("Campaign",      back_populates="spacing_rules")
    combinations: Mapped[list["Combination"]] = relationship("Combination", back_populates="spacing_rule")


# ---------------------------------------------------------------------------
# CampaignKeywordPick
# ---------------------------------------------------------------------------

class CampaignKeywordPick(Base):
    __tablename__ = "campaign_keyword_picks"
    __table_args__ = (
        UniqueConstraint("campaign_id", "keyword_id", name="uq_pick"),
    )

    id:          Mapped[int]      = mapped_column(Integer,  primary_key=True, autoincrement=True)
    campaign_id: Mapped[int]      = mapped_column(Integer,  ForeignKey("campaigns.id"),          nullable=False)
    category_id: Mapped[int]      = mapped_column(Integer,  ForeignKey("keyword_categories.id"), nullable=False)
    keyword_id:  Mapped[int]      = mapped_column(Integer,  ForeignKey("keywords.id"),           nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    campaign: Mapped["Campaign"]        = relationship("Campaign",        back_populates="picks")
    category: Mapped["KeywordCategory"] = relationship("KeywordCategory", back_populates="picks")
    keyword:  Mapped["Keyword"]         = relationship("Keyword",         back_populates="picks")


# ---------------------------------------------------------------------------
# Combination
# ---------------------------------------------------------------------------

class Combination(Base):
    __tablename__ = "combinations"

    id:              Mapped[int]           = mapped_column(BigInteger,      primary_key=True, autoincrement=True)
    campaign_id:     Mapped[int]           = mapped_column(Integer,     ForeignKey("campaigns.id"),      nullable=False)
    spacing_rule_id: Mapped[Optional[int]] = mapped_column(Integer,     ForeignKey("spacing_rules.id"),  nullable=True)
    config:          Mapped[dict[str, Any] | None]= mapped_column(JSON,        nullable=True)
    used_at:         Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at:      Mapped[datetime]      = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    campaign:      Mapped["Campaign"]        = relationship("Campaign",      back_populates="combinations")
    spacing_rule:  Mapped[Optional["SpacingRule"]] = relationship("SpacingRule", back_populates="combinations")
    keywords:      Mapped[list["Keyword"]]   = relationship(
        "Keyword", secondary=combination_keywords, back_populates="combinations"
    )
    batch_items:   Mapped[list["BatchItem"]] = relationship("BatchItem", back_populates="combination")


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

class Batch(Base):
    __tablename__ = "batches"

    id:           Mapped[int]           = mapped_column(Integer,    primary_key=True, autoincrement=True)
    campaign_id:  Mapped[int]           = mapped_column(Integer,    ForeignKey("campaigns.id"),  nullable=False)
    account_id:   Mapped[int]           = mapped_column(Integer,    ForeignKey("accounts.id"),   nullable=False)
    scheduled_at: Mapped[datetime]      = mapped_column(DateTime,   nullable=False)
    status:       Mapped[str]           = mapped_column(String(16), nullable=False, default="pending")
    worker_pid:   Mapped[Optional[int]] = mapped_column(Integer,    nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # relationships
    account:  Mapped["Account"]        = relationship("Account",  back_populates="batches")
    campaign: Mapped["Campaign"]       = relationship("Campaign", back_populates="batches")
    items:    Mapped[list["BatchItem"]]= relationship("BatchItem", back_populates="batch")


# ---------------------------------------------------------------------------
# BatchItem
# ---------------------------------------------------------------------------

class BatchItem(Base):
    __tablename__ = "batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "combination_id", name="uq_batch_combo"),
    )

    id:             Mapped[int]           = mapped_column(BigInteger,       primary_key=True, autoincrement=True)
    batch_id:       Mapped[int]           = mapped_column(Integer,      ForeignKey("batches.id"),       nullable=False)
    combination_id: Mapped[int]           = mapped_column(BigInteger,       ForeignKey("combinations.id"),  nullable=False)
    status:         Mapped[str]           = mapped_column(String(16),   nullable=False, default="pending")
    result_url:     Mapped[Optional[str]] = mapped_column(String(512),  nullable=True)
    error_message:  Mapped[Optional[str]] = mapped_column(Text,         nullable=True)
    created_at:     Mapped[datetime]      = mapped_column(DateTime,     nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # relationships
    batch:       Mapped["Batch"]       = relationship("Batch",       back_populates="items")
    combination: Mapped["Combination"] = relationship("Combination", back_populates="batch_items")


# ---------------------------------------------------------------------------
# Affix — global affix dictionary (prefix/suffix values)
# ---------------------------------------------------------------------------

class Affix(Base):
    __tablename__ = "affixes"
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_affix_type_value"),
    )

    id:         Mapped[int]      = mapped_column(Integer,    primary_key=True, autoincrement=True)
    type:       Mapped[str]      = mapped_column(String(16), nullable=False)  # "prefix" | "suffix"
    value:      Mapped[str]      = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int]      = mapped_column(Integer,    nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime,   nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    keywords: Mapped[list["Keyword"]] = relationship(
        "Keyword", secondary=keyword_affixes, back_populates="affixes",
    )
    overrides: Mapped[list["CampaignAffixOverride"]] = relationship(
        "CampaignAffixOverride", back_populates="affix",
    )


# ---------------------------------------------------------------------------
# CampaignAffixOverride — per-campaign, per-keyword affix toggle
# ---------------------------------------------------------------------------

class CampaignAffixOverride(Base):
    __tablename__ = "campaign_affix_overrides"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "keyword_id", "affix_id",
            name="uq_campaign_keyword_affix",
        ),
    )

    id:          Mapped[int]      = mapped_column(Integer,  primary_key=True, autoincrement=True)
    campaign_id: Mapped[int]      = mapped_column(Integer,  ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    keyword_id:  Mapped[int]      = mapped_column(Integer,  ForeignKey("keywords.id", ondelete="CASCADE"),  nullable=False)
    affix_id:    Mapped[int]      = mapped_column(Integer,  ForeignKey("affixes.id", ondelete="CASCADE"),   nullable=False)
    active:      Mapped[bool]     = mapped_column(Boolean,  nullable=False, default=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="affix_overrides")
    keyword:  Mapped["Keyword"]  = relationship("Keyword")
    affix:    Mapped["Affix"]    = relationship("Affix",    back_populates="overrides")


# ---------------------------------------------------------------------------
# CampaignPalette — runtime sampling pool for a token
# ---------------------------------------------------------------------------

class CampaignPalette(Base):
    __tablename__ = "campaign_palettes"

    token_id:   Mapped[int] = mapped_column(Integer,    ForeignKey("template_tokens.id", ondelete="CASCADE"), primary_key=True)
    strategy:   Mapped[str] = mapped_column(String(16), nullable=False, default="random")  # "random" | "sequential"
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    token: Mapped["TemplateToken"]         = relationship("TemplateToken", back_populates="palette")
    items: Mapped[list["PaletteItem"]]     = relationship(
        "PaletteItem", back_populates="palette", order_by="PaletteItem.sort_order",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# PaletteItem — individual value in a palette
# ---------------------------------------------------------------------------

class PaletteItem(Base):
    __tablename__ = "palette_items"

    id:         Mapped[int]      = mapped_column(Integer,     primary_key=True, autoincrement=True)
    palette_id: Mapped[int]      = mapped_column(Integer,     ForeignKey("campaign_palettes.token_id", ondelete="CASCADE"), nullable=False)
    value:      Mapped[str]      = mapped_column(String(256), nullable=False)
    sort_order: Mapped[int]      = mapped_column(Integer,     nullable=False, default=0)
    active:     Mapped[bool]     = mapped_column(Boolean,     nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime,    nullable=False, default=lambda: datetime.now(timezone.utc))

    # relationships
    palette: Mapped["CampaignPalette"] = relationship("CampaignPalette", back_populates="items")
