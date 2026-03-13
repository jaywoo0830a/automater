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
from typing import Literal


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

ThumbnailLayout = Literal[
    "왼쪽오른쪽", "왼쪽 위", "오른쪽 위", "오른쪽 중앙",
    "오른쪽 아래", "오른테 위", "정중앙", "가운테 아래",
    "왼쪽 중앙", "왼쪽 아래",
]

UidVariation = Literal["5%", "25%", "50%"]


@dataclass(frozen=True)
class ContentOption:
    """Rules for generating post body content and images."""
    preview_images:       list[str]       = field(default_factory=list)
    thumbnail_image:      str | None      = None
    thumbnail_layout:     ThumbnailLayout = "왼쪽오른쪽"
    paragraph_count:      int             = 5
    min_paragraph_length: int             = 5
    max_paragraph_length: int             = 10
    uid_variation:        UidVariation    = "5%"
    seo_exif:             bool            = False
    seo_filename:         bool            = False
    seo_alt_text:         bool            = False
    watermark_body:       bool            = False
    watermark_thumbnail:  bool            = False
    extra_prompt:         str             = ""


# ---------------------------------------------------------------------------
# MetaOption
# ---------------------------------------------------------------------------

TagStyle = Literal[
    "dynamic", "education", "region", "subject", "learning_type",
]


@dataclass(frozen=True)
class MetaOption:
    """Rules for post metadata: tags, backlinks, internal links."""
    min_tags:            int      = 12
    max_tags:            int      = 20
    tag_style:           TagStyle = "dynamic"
    backlink_ratio:      int      = 0
    internal_link_ratio: int      = 0


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
