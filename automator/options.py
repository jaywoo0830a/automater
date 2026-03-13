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
dataclasses.replace():

    new_job = replace(job, _title=TitleOption(extra_prompt="새 제목"))

No I/O, no Playwright, no imports beyond stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# AccountOption — 계정 설정
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountOption:
    """
    Naver account credentials and per-account posting quota.

    Attributes:
        naver_id:   Naver login ID.
        naver_pw:   Naver login password.
        blog_id:    Blog ID used to construct the write URL.
                    e.g. "rlawjddn00az" → blog.naver.com/rlawjddn00az
        post_count: Number of posts to publish with this account.
        proxies:    Proxy addresses ("ip:port") to cycle through.
                    Empty list means no proxy.
        session_path: Path to Playwright storage-state JSON.
                      Defaults to "<naver_id>_session.json".
    """
    naver_id:     str
    naver_pw:     str
    blog_id:      str
    post_count:   int       = 1
    proxies:      list[str] = field(default_factory=list)
    session_path: str       = ""   # empty → auto-derived in NaverBlogJob

    @property
    def write_url(self) -> str:
        """Naver blog write URL for this account."""
        return f"https://blog.naver.com/{self.blog_id}?Redirect=Write&"

    @property
    def resolved_session_path(self) -> str:
        """Return session_path, falling back to '<naver_id>_session.json'."""
        return self.session_path or f"{self.naver_id}_session.json"


# ---------------------------------------------------------------------------
# TitleOption — 제목 설정
# ---------------------------------------------------------------------------

TitleTemplate = Literal[
    "지역+과목+학습형태+솔트",
    "과목+지역+학습형태+솔트",
]

RegionScope = Literal[
    "핵심 시군구",
    "전국 시군구",
    "전국 읍면읍",
]

LearningType = Literal["과외", "학원"]


@dataclass(frozen=True)
class TitleOption:
    """
    Rules for generating the post title.

    Attributes:
        template:         Keyword assembly order.
        region_scope:     Which administrative units to draw region names from.
        include_particle: Whether to append a Korean location particle.
        subjects:         Subject names to cycle through (e.g. ["국어", "수학"]).
        learning_type:    과외 or 학원.
        salts:            Modifier keywords to vary the title.
        min_length:       Minimum character count for a generated title.
        max_length:       Maximum character count for a generated title.
        has_space:        Whether spaces are allowed between keywords.
        add_particle:     Whether to prepend/append a location particle.
        randomize_chars:  Whether to substitute random lookalike characters.
        extra_prompt:     Free-text hint passed to the AI title generator.
    """
    template:         TitleTemplate = "지역+과목+학습형태+솔트"
    region_scope:     RegionScope   = "핵심 시군구"
    include_particle: bool          = True
    subjects:         list[str]     = field(default_factory=list)
    learning_type:    LearningType  = "과외"
    salts:            list[str]     = field(default_factory=lambda: ["완벽", "인기", "즉시"])
    min_length:       int           = 12
    max_length:       int           = 24
    has_space:        bool          = True
    add_particle:     bool          = True
    randomize_chars:  bool          = True
    extra_prompt:     str           = ""


# ---------------------------------------------------------------------------
# ContentOption — 내용 설정
# ---------------------------------------------------------------------------

ThumbnailLayout = Literal[
    "왼쪽오른쪽", "왼쪽 위", "오른쪽 위", "오른쪽 중앙",
    "오른쪽 아래", "오른테 위", "정중앙", "가운테 아래",
    "왼쪽 중앙", "왼쪽 아래",
]

UidVariation = Literal["5%", "25%", "50%"]


@dataclass(frozen=True)
class ContentOption:
    """
    Rules for generating post body content and images.

    Attributes:
        preview_images:       Paths to body images (displayed in order).
        thumbnail_image:      Path to the representative/thumbnail image.
        thumbnail_layout:     Where to place the thumbnail relative to body text.
        paragraph_count:      Number of AI-generated paragraphs.
        min_paragraph_length: Minimum character count per paragraph.
        max_paragraph_length: Maximum character count per paragraph.
        uid_variation:        How aggressively to vary invisible characters.
        seo_exif:             Embed SEO data in image EXIF.
        seo_filename:         Rename image files for SEO.
        seo_alt_text:         Inject AI-generated alt text.
        watermark_body:       Add watermark to body images.
        watermark_thumbnail:  Add watermark to thumbnail image.
        extra_prompt:         Free-text hint passed to the AI content generator.
    """
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
# MetaOption — 메타데이터 설정
# ---------------------------------------------------------------------------

TagStyle = Literal[
    "dynamic",       # 본문 언급 단어 기반 동적 생성
    "education",     # 교육 관련 태그
    "region",        # 지역 관련 태그
    "subject",       # 과목 관련 태그
    "learning_type", # 학습 형태 관련 태그
]


@dataclass(frozen=True)
class MetaOption:
    """
    Rules for post metadata: tags, backlinks, internal links.

    Attributes:
        min_tags:            Minimum number of tags to generate.
        max_tags:            Maximum number of tags to generate.
        tag_style:           Strategy for tag generation.
        backlink_ratio:      0–100. Probability (%) that a backlink is injected.
        internal_link_ratio: 0–100. Probability (%) of an internal link.
    """
    min_tags:            int      = 12
    max_tags:            int      = 20
    tag_style:           TagStyle = "dynamic"
    backlink_ratio:      int      = 0
    internal_link_ratio: int      = 0


# ---------------------------------------------------------------------------
# RunSetting — 실행 설정
# ---------------------------------------------------------------------------

OnFailure = Literal[
    "stop",           # 즉시 중단
    "switch_account", # 다른 계정으로 변경해서 계속
]


@dataclass(frozen=True)
class RunSetting:
    """
    Runtime behaviour: scheduling, throttling, failure handling, browser.

    Attributes:
        scheduled:          Whether to use scheduled (delayed) publishing.
        schedule_interval:  Hours between scheduled publish times.
        post_interval:      Seconds to wait between consecutive posts.
        max_daily_posts:    Hard cap on posts per calendar day.
        on_failure:         What to do when a post fails.
        rotate_user_agent:  Randomly pick a User-Agent string each run.
        headless:           Run browser in headless mode.
        slow_mo:            Milliseconds to slow down Playwright actions.
    """
    scheduled:         bool      = True
    schedule_interval: int       = 12   # hours
    post_interval:     int       = 60   # seconds
    max_daily_posts:   int       = 10
    on_failure:        OnFailure = "stop"
    rotate_user_agent: bool      = True
    headless:          bool      = True
    slow_mo:           int       = 0
