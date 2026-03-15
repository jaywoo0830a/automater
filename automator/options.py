"""
automator/options.py
---------------------
Value objects that describe a blog posting job.

Each dataclass maps directly to one configuration step in the UI:

    AccountOption  ← 계정 설정
    TitleOption    ← 제목 설정
    ContentOption  ← 내용 설정
    MetaOption     ← 메타데이터 설정
    RunSetting     ← 기타 실행 설정

All dataclasses are frozen (immutable). To modify a value, use
dataclasses.replace().

No I/O, no Playwright, no imports beyond stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

# Korean Standard Time (UTC+9) — use for all schedule_at values
KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# AccountOption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountOption:
    """
    Naver account credentials and per-account posting quota.

    Attributes:
        naver_id:     Naver login ID.
        naver_pw:     Naver login password.
        blog_id:      Blog ID used to construct the write URL.
        post_count:   Number of posts to publish with this account.
        proxies:      Proxy addresses ("ip:port") to cycle through.
        session_path: Path to Playwright storage-state JSON.
                      Defaults to "<naver_id>_session.json".
    """
    naver_id:     str
    naver_pw:     str
    blog_id:      str
    post_count:   int       = 1
    proxies:      list[str] = field(default_factory=list)
    session_path: str       = ""

    @property
    def write_url(self) -> str:
        return f"https://blog.naver.com/{self.blog_id}?Redirect=Write&"

    @property
    def resolved_session_path(self) -> str:
        return self.session_path or f"{self.naver_id}_session.json"


# ---------------------------------------------------------------------------
# TitleOption
# ---------------------------------------------------------------------------

# Valid token names that can appear in a template string
TITLE_TOKENS = frozenset({"지역", "과목", "학습형태", "솔트"})

LearningType = Literal["과외", "학원"]


@dataclass(frozen=True)
class TitleOption:
    """
    Rules for generating a blog post title for SEO keyword targeting.

    목적: "대치동 영어 과외 강력 추천" 같은 검색 키워드 기반 제목을 생성한다.

    Preset files (JSON)
    -------------------
    세 가지 프리셋을 JSON 파일로 관리한다. 경로를 비워두면
    TitleGenerator가 presets/title/ 의 기본 파일을 사용한다.

    region_preset:  regions.json  — [{base_name, full_name, tier}, ...]
    subject_preset: subjects.json — [과목명, ...]
    salt_preset:    salts.json    — [솔트 텍스트, ...]

    Assembly rules
    --------------
    template:
        '+' 로 구분된 토큰 순서 문자열. 유효 토큰: 지역, 과목, 학습형태, 솔트.
        네 토큰 모두 반드시 포함해야 한다.

        기본값:  "지역+과목+학습형태+솔트"  → "대치동 영어 과외 강력 추천"
        솔트 앞: "솔트+지역+과목+학습형태"  → "강력 추천 대치동 영어 과외"
        트렌드에 따라 자유롭게 순서를 변경할 수 있다.

    learning_type:
        "과외" or "학원". 항상 포함. 트렌드에 따라 변경 가능.

    include_suffix:
        True  → full_name 사용 ("대치동", "강남구") — 행정구역 단위 포함
        False → base_name 사용 ("대치", "강남")     — 단위 제외

    Stub features (구현 예정 — 현재는 무시됨)
    ------------------------------------------
    has_space:        토큰 사이 공백 삽입 여부.
    add_affix:        제목 앞뒤에 랜덤 조사/어미 추가 여부.
    randomize_chars:  유사 문자 치환 여부 (스팸 필터 우회용).
    ai_preset_prompt: Gemini API로 추가 프리셋을 생성할 때 쓸 프롬프트.
    """
    # Preset file paths (empty string → TitleGenerator uses built-in default)
    region_preset:  str = ""
    subject_preset: str = ""
    salt_preset:    str = ""

    # Assembly rules
    template:       str          = "지역+과목+학습형태+솔트"
    learning_type:  LearningType = "과외"
    include_suffix: bool         = True   # True=대치동, False=대치

    # Direct override — skips TitleGenerator entirely when set
    fixed_title: str = ""           # non-empty → use this string as-is

    # Stub features
    has_space:        bool = True   # stub: always True for now
    add_affix:        bool = False  # stub: not yet implemented
    randomize_chars:  bool = False  # stub: not yet implemented
    ai_preset_prompt: str  = ""     # stub: Gemini API preset generation


# ---------------------------------------------------------------------------
# ContentOption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentOption:
    """
    Rules for generating post body content and image layout.

    Fields
    ------
    preview_images:
        본문에 삽입할 이미지 경로 리스트.
        alias: "Image 1", "Image 2", ... (인덱스+1 순서로 자동 부여)

    thumbnail_images:
        썸네일 베이스 이미지 경로 리스트.
        alias: "Thumbnail 1", "Thumbnail 2", ...
        현재는 1장만 사용하지만, 네이버 정책 변경 대비 리스트로 관리.

    layout:
        alias 문자열 리스트로 포스트 내용의 순서를 지정한다.
        유효 alias:
          "Image N"       — preview_images[N-1] 업로드
          "Thumbnail N"   — thumbnail_images[N-1] 업로드 (대표 이미지)
          "Paragraph N"   — N번째 AI 생성 단락 삽입
        파라그래프 개수는 layout 내 "Paragraph N" 최대 번호로 자동 결정된다.

        예시:
          ["Image 1", "Image 2", "Paragraph 1", "Thumbnail 1",
           "Paragraph 2", "Paragraph 3"]
          → 이미지 2장 → 단락 1 → 썸네일 → 단락 2, 3

        빈 리스트이면 콘텐츠 없이 제목과 본문만 게시된다.
    """
    preview_images:    list[str] = field(default_factory=list)
    thumbnail_images:  list[str] = field(default_factory=list)
    layout:            list[str] = field(default_factory=list)
    paragraph_newlines: int      = 2  # Enter presses appended after each paragraph
    paragraph_prompt:   str      = ""  # Gemini prompt for paragraph generation; empty = placeholder


# ---------------------------------------------------------------------------
# MetaOption
# ---------------------------------------------------------------------------

TagStyle = Literal[
    "dynamic", "education", "region", "subject", "learning_type",
]

ScheduleMode = Literal[
    "immediate",      # publish immediately (default — existing behaviour)
    "fixed",          # publish at exactly schedule_at
    "random_window",  # publish at a random time within schedule_at ± jitter
]


@dataclass(frozen=True)
class MetaOption:
    """
    Rules for post metadata: tags, backlinks, internal links, publish schedule.

    Publish schedule
    ----------------
    schedule_mode = "immediate"  (default)
        Publish immediately. schedule_at and schedule_jitter_minutes are ignored.

    schedule_mode = "fixed"
        Reserve the post at the exact KST datetime given in schedule_at.
        schedule_at must be a timezone-aware future datetime. (validated by job)

    schedule_mode = "random_window"
        Pick a random datetime within schedule_at ± schedule_jitter_minutes and
        reserve the post at that time. Useful for evading spam-detection patterns
        caused by identical posting times across multiple accounts.
        schedule_at must be timezone-aware, and schedule_at - jitter must be in
        the future. (validated by job)

    Notes:
        - schedule_at must always be a timezone-aware datetime.
        - Recommended timezone: KST  (from automator.options import KST)
        - NaverBlogJob.validate() raises ValueError for any constraint violation.
    """

    # --- existing fields (unchanged) ---
    min_tags:            int      = 12
    max_tags:            int      = 20
    tag_style:           TagStyle = "dynamic"
    backlink_ratio:      int      = 0
    internal_link_ratio: int      = 0

    # --- publish schedule ---
    schedule_mode:           ScheduleMode    = "immediate"
    schedule_at:             datetime | None = None
    schedule_jitter_minutes: int             = 30


# ---------------------------------------------------------------------------
# RunSetting
# ---------------------------------------------------------------------------

OnFailure = Literal["stop", "switch_account"]


@dataclass(frozen=True)
class RunSetting:
    """Runtime behaviour: scheduling, throttling, failure handling, browser."""
    scheduled:         bool      = True
    schedule_interval: int       = 12
    post_interval:     int       = 60
    max_daily_posts:   int       = 10
    on_failure:        OnFailure = "stop"
    rotate_user_agent: bool      = True
    headless:          bool      = True
    slow_mo:           int       = 0
