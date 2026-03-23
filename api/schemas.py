"""
api/schemas.py — Pydantic v2 models. Maps to api_spa_v1.yaml components/schemas.
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

# -- Common -------------------------------------------------------------------
class FriendlyError(BaseModel):
    success: bool = False
    message: str
    suggestion: str = ""

class ActionResult(BaseModel):
    success: bool
    message: str

# -- Auth ---------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str

class LoginUser(BaseModel):
    display_name: str
    email: str

class LoginResponse(BaseModel):
    token: str
    user: LoginUser

# -- Step 1 -------------------------------------------------------------------
class AccountRowPreview(BaseModel):
    row_number: int
    username: str
    platform: str
    blog_id: str = ""
    valid: bool
    error: str | None = None

class AccountUploadPreview(BaseModel):
    success: bool
    rows: list[AccountRowPreview]
    valid_count: int
    invalid_count: int

class AccountData(BaseModel):
    username: str
    password: str
    platform: str
    blog_id: str = ""
    cooldown_days: int = 14

class AccountConfirmInput(BaseModel):
    accounts: list[AccountData]
    selected: list[int]

class AccountConfirmResult(BaseModel):
    success: bool
    message: str
    saved_count: int
    selected_count: int

class AccountView(BaseModel):
    id: int
    username: str
    platform: str
    status: str
    selected: bool
    last_used: str | None = None

class AccountSelectInput(BaseModel):
    account_ids: list[int]

# -- Step 2a: Keywords + Affixes ----------------------------------------------
class AffixInfo(BaseModel):
    affix_id: int
    type: str
    value: str
    active: bool = True
    stripped_result: str = ""

class KeywordItem(BaseModel):
    id: int
    value: str
    display_value: str = ""
    active: bool = True
    affixes: list[AffixInfo] = Field(default_factory=list)

class CategoryPreview(BaseModel):
    column_name: str
    slug: str
    keyword_count: int
    sample_values: list[str]
    detected_affixes: list[str]

class KeywordUploadPreview(BaseModel):
    success: bool
    categories: list[CategoryPreview]
    total_keywords: int

class CategoryImport(BaseModel):
    slug: str
    name: str = ""
    values: list[str]

class KeywordImportInput(BaseModel):
    categories: list[CategoryImport]
    auto_detect_affixes: bool = True

class KeywordImportResult(BaseModel):
    success: bool
    message: str
    categories_created: int
    keywords_created: int
    keywords_existing: int
    affixes_linked: int = 0

class KeywordCategoryView(BaseModel):
    slug: str
    name: str
    keywords: list[KeywordItem]

class KeywordAddInput(BaseModel):
    value: str

class KeywordEditInput(BaseModel):
    value: str | None = None
    active: bool | None = None

class AffixOverrideEntry(BaseModel):
    keyword_id: int
    affix_id: int
    active: bool

class AffixOverrideInput(BaseModel):
    overrides: list[AffixOverrideEntry]

class AffixOverrideResult(BaseModel):
    success: bool
    message: str
    updated_count: int

# -- Step 2b: Pools -----------------------------------------------------------
class PoolItemView(BaseModel):
    id: int
    value: str
    active: bool = True
    sort_order: int = 0

class PoolView(BaseModel):
    slug: str
    strategy: str = "random"
    items: list[PoolItemView]

class PoolCreatedInfo(BaseModel):
    slug: str
    created_count: int
    samples: list[str]

class PoolUploadResult(BaseModel):
    success: bool
    message: str
    pools: list[PoolCreatedInfo]

class PoolItemAddInput(BaseModel):
    value: str

class PoolItemEditInput(BaseModel):
    value: str | None = None
    active: bool | None = None

# -- Step 2c: Spacing ---------------------------------------------------------
class SpacingStyle(BaseModel):
    name: str = ""
    pattern: dict[str, int]

class KeywordSelection(BaseModel):
    slug: str
    keyword_ids: list[int]

class SpacingPreviewInput(BaseModel):
    styles: list[SpacingStyle]
    token_slugs: list[str]
    keyword_selections: list[KeywordSelection] = Field(default_factory=list)
    count: int = 3

class SpacingStylePreview(BaseModel):
    name: str
    template: str
    samples: list[str]

class SpacingPreviewResult(BaseModel):
    styles: list[SpacingStylePreview]
    combination_multiplier: int
    warnings: list[str]

# -- Step 2d: Title ------------------------------------------------------------
class TitleTokenInput(BaseModel):
    type: str
    slug: str
    value: str = ""
    sort_order: int = 0

class TitlePreviewInput(BaseModel):
    title_tokens: list[TitleTokenInput]
    keyword_selections: list[KeywordSelection] = Field(default_factory=list)
    spacing_styles: list[SpacingStyle] = Field(default_factory=list)
    affix_overrides: list[AffixOverrideEntry] = Field(default_factory=list)
    count: int = 3

class TitlePreviewResult(BaseModel):
    styles: list[SpacingStylePreview]
    total_combinations: int
    warnings: list[str]

# -- Step 2 Confirm -----------------------------------------------------------
class Step2ConfirmInput(BaseModel):
    campaign_name: str
    platform_id: int
    keyword_selections: list[KeywordSelection]
    title_tokens: list[TitleTokenInput]
    spacing_styles: list[SpacingStyle]
    affix_overrides: list[AffixOverrideEntry] = Field(default_factory=list)

class Step2ConfirmResult(BaseModel):
    success: bool
    message: str
    campaign_id: int
    title_template: str
    spacing_style_count: int
    combination_count: int

# -- Step 3 -------------------------------------------------------------------
class TemplateView(BaseModel):
    id: int
    name: str
    description: str = ""
    block_summary: str = ""

class BlockDetail(BaseModel):
    order: int
    type: str
    label: str = ""
    config_summary: str | None = None

class TemplateDetailView(BaseModel):
    id: int
    name: str
    description: str = ""
    blocks: list[BlockDetail]

class PostBlockPreview(BaseModel):
    type: str
    placeholder: str

class PostPreview(BaseModel):
    sample_title: str
    blocks: list[PostBlockPreview]

# -- Step 4 -------------------------------------------------------------------
class RunConfig(BaseModel):
    campaign_id: int
    template_id: int
    publish_mode: str
    schedule_start: datetime | None = None
    schedule_interval_minutes: int = 60
    headless: bool = True

class AccountAssignment(BaseModel):
    username: str
    posts_assigned: int

class RunPreviewView(BaseModel):
    campaign_name: str
    template_name: str
    total_combinations: int
    accounts: list[AccountAssignment]
    publish_mode: str
    schedule_summary: str | None = None
    estimated_finish: str | None = None
    sample_titles: list[str]
    warnings: list[str]

class RunStartResult(BaseModel):
    success: bool
    message: str
    batch_ids: list[int]
    total_posts: int

# -- Monitor ------------------------------------------------------------------
class RunProgressView(BaseModel):
    batch_id: int
    campaign_name: str
    account: str
    status: str
    completed: int
    failed: int
    total: int
    percentage: int
    started_at: str | None = None
    last_activity: str = ""

class PostingItemView(BaseModel):
    title: str
    keywords: str
    status: str
    url: str | None = None
    error: str | None = None
    completed_at: str | None = None

class RunDetailView(BaseModel):
    batch_id: int
    campaign_name: str
    account: str
    status: str
    completed: int
    failed: int
    total: int
    items: list[PostingItemView]
