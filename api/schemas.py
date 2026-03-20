"""
api/schemas.py
---------------
Pydantic v2 models for API request/response serialization.
Matches the OpenAPI 3.2.0 spec schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str
    role: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None

class UserUpdate(BaseModel):
    display_name: str | None = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

class AdminUserUpdate(BaseModel):
    role: str | None = None
    status: str | None = None


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class Paginated(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

class PlatformOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    base_url: str
    status: str


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class AccountCreate(BaseModel):
    platform_id: int
    username: str
    password: str
    meta: dict[str, Any] | None = None

class AccountUpdate(BaseModel):
    password: str | None = None
    meta: dict[str, Any] | None = None
    cooldown_days: int | None = None
    status: str | None = None
    note: str | None = None

class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    platform_id: int
    username: str
    meta: dict[str, Any] | None = None
    cooldown_days: int
    last_used_at: datetime | None = None
    status: str
    note: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str
    slug: str

class CategoryUpdate(BaseModel):
    name: str | None = None

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str

class KeywordCreate(BaseModel):
    value: str
    display_value: str = ""
    parent_id: int | None = None
    tier: int = 1
    metadata: dict[str, Any] | None = None

class KeywordUpdate(BaseModel):
    value: str | None = None
    display_value: str | None = None
    parent_id: int | None = None
    tier: int | None = None
    active: bool | None = None
    sort_order: int | None = None
    metadata: dict[str, Any] | None = None

class AffixOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    keyword_id: int
    type: str
    value: str
    sort_order: int
    active: bool

class KeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    parent_id: int | None = None
    value: str
    display_value: str
    tier: int
    active: bool
    sort_order: int
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    children: list[KeywordOut] = []
    affixes: list[AffixOut] = []

class AffixCreate(BaseModel):
    type: str
    value: str
    sort_order: int = 0

class AffixUpdate(BaseModel):
    value: str | None = None
    sort_order: int | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------

class LayoutSlotIn(BaseModel):
    sort_order: int
    block_type: str
    config: dict[str, Any] | None = None

class LayoutSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    layout_id: int
    sort_order: int
    block_type: str
    config: dict[str, Any] | None = None

class LayoutCreate(BaseModel):
    name: str
    description: str | None = None
    slots: list[LayoutSlotIn] = []

class LayoutUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

class LayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    description: str | None = None
    slots: list[LayoutSlotOut] = []
    created_at: datetime

class PreviewRequest(BaseModel):
    values: dict[str, str] = {}

class RenderedBlock(BaseModel):
    block_type: str
    rendered_config: dict[str, Any]


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

class PresetCreate(BaseModel):
    name: str
    description: str | None = None
    config: dict[str, Any]

class PresetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None

class PublishPresetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    description: str | None = None
    config: dict[str, Any]
    created_at: datetime

class RunPresetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    description: str | None = None
    config: dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

class CampaignCreate(BaseModel):
    platform_id: int
    name: str
    description: str | None = None
    title_template: str = ""
    layout_id: int | None = None
    publish_preset_id: int | None = None
    run_preset_id: int | None = None
    config: dict[str, Any] | None = None

class CampaignUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    title_template: str | None = None
    layout_id: int | None = Field(None)
    publish_preset_id: int | None = Field(None)
    run_preset_id: int | None = Field(None)
    status: str | None = None
    config: dict[str, Any] | None = None

class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    platform_id: int
    layout_id: int | None = None
    publish_preset_id: int | None = None
    run_preset_id: int | None = None
    name: str
    description: str | None = None
    title_template: str
    config: dict[str, Any] | None = None
    status: str
    created_at: datetime
    layout: LayoutOut | None = None
    publish_preset: PublishPresetOut | None = None
    run_preset: RunPresetOut | None = None

class CloneRequest(BaseModel):
    name: str | None = None

class CampaignStats(BaseModel):
    total_combinations: int = 0
    pending_combinations: int = 0
    total_batches: int = 0
    completed_batches: int = 0
    failed_items: int = 0
    success_rate: float = 0.0

class PreviewTitleRequest(BaseModel):
    values: dict[str, str] = {}
    seed: int | None = None


# ---------------------------------------------------------------------------
# Campaign sub-resources
# ---------------------------------------------------------------------------

class CampaignSlotIn(BaseModel):
    category_id: int
    sort_order: int

class CampaignSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    campaign_id: int
    category_id: int
    sort_order: int
    category: CategoryOut | None = None

class PicksRequest(BaseModel):
    category_slug: str
    values: list[str]

class PaletteItemIn(BaseModel):
    value: str
    sort_order: int = 0
    active: bool = True

class PaletteItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    palette_id: int
    value: str
    sort_order: int
    active: bool

class PaletteCreate(BaseModel):
    slug: str
    strategy: str = "random"
    items: list[PaletteItemIn] = []

class PaletteUpdate(BaseModel):
    strategy: str | None = None

class PaletteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int
    slug: str
    strategy: str
    items: list[PaletteItemOut] = []

class SpacingRuleCreate(BaseModel):
    pattern: dict[str, Any]
    description: str = ""
    active: bool = True

class SpacingRuleUpdate(BaseModel):
    pattern: dict[str, Any] | None = None
    description: str | None = None
    active: bool | None = None

class SpacingRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int
    pattern: dict[str, Any]
    description: str
    active: bool


# ---------------------------------------------------------------------------
# Combinations
# ---------------------------------------------------------------------------

class SeedResult(BaseModel):
    created: int

class ClearResult(BaseModel):
    deleted: int

class SeedPreview(BaseModel):
    total: int
    by_category: dict[str, int]

class CombinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int
    spacing_rule_id: int | None = None
    used_at: datetime | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------

class DispatchRequest(BaseModel):
    schedule_base: datetime

class DispatchResult(BaseModel):
    batches_created: int
    accounts_used: int
    combos_assigned: int

class BatchItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_id: int
    combination_id: int
    status: str
    result_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    campaign_id: int
    account_id: int
    scheduled_at: datetime
    status: str
    worker_pid: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[BatchItemOut] = []


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

class TemplateValidation(BaseModel):
    valid: bool
    tokens: list[str] = []
    error: str | None = None

class BlockTypeInfo(BaseModel):
    type: str
    label: str
    config_schema: dict[str, Any] = {}
