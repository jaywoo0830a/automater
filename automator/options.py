"""
automator/options.py
---------------------
Frozen value objects — no I/O, no imports beyond stdlib.

Public interface
----------------
    AccountOption       — who is posting
    TitleOption         — title template + pools
    Section             — block container (role, tone)
    PublishOption       — schedule, tags, visibility
    RunSetting          — throttling, failure handling

Block types (inside Section.blocks)
------------------------------------
    HeadingBlock        — H1-H6
    ParagraphBlock      — AI-generated text
    ImageBlock          — body image
    FeaturedImageBlock  — thumbnail image
    ListBlock           — ordered/unordered list
    QuoteBlock          — blockquote
    DividerBlock        — horizontal rule

Type aliases
------------
    Block      = Union of all block types
    BlockRole  = Literal["intro", "body", "supporting", "cta", "closing"]
    BlockTone  = Literal["informational", "review", "story", "promotional"]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal, Union

KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# AccountOption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountOption:
    """
    Platform-agnostic account credentials.

    Attributes:
        username:     Login username / ID.
        password:     Login password.
        meta:         Platform-specific extras.
                      Naver    → {"blog_id": "rlawjddn"}
                      WordPress → {"api_url": "https://...", "api_key": "..."}
        proxies:      "ip:port" list to cycle through.
        session_path: Playwright storage-state JSON path.
                      Defaults to "<username>_session.json".
    """
    username:     str
    password:     str
    meta:         dict      = field(default_factory=dict)
    proxies:      list[str] = field(default_factory=list)
    session_path: str       = ""

    @property
    def resolved_session_path(self) -> str:
        """Return explicit session_path or default '<username>_session.json'."""
        return self.session_path or f"{self.username}_session.json"

    def session_exists(self) -> bool:
        """Return True if the resolved session file exists on disk."""
        from pathlib import Path
        return Path(self.resolved_session_path).exists()


# ---------------------------------------------------------------------------
# TitleOption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TitleOption:
    """
    Rules for generating a post title.

    Template DSL
    ------------
    {keyword:slug}  — substituted from ``values[slug]`` (deterministic).
    {pool:slug}     — random choice from ``pools[slug]``.
    plain text      — kept as-is.  Spacing is what you type.

    Pools data is supplied directly — no file I/O.
    Loaded from CampaignPalette rows before constructing this option.

    Examples::

        TitleOption(
            template="{pool:salt_prefix} {keyword:region} {keyword:subject} 과외 {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학"},
            pools={
                "salt_prefix": ("검증된", "전문"),
                "salt_suffix": ("강력 추천", "즉시 가능"),
            },
        )
        TitleOption(fixed_title="강남 수학 과외 추천")
    """
    template:         str              = ""
    values:           dict             = field(default_factory=dict)
    pools:            dict[str, tuple[str, ...]] = field(default_factory=dict)
    fixed_title:      str              = ""
    add_affix:        bool             = False
    randomize_chars:  bool             = False
    ai_preset_prompt: str              = ""
    seed:             int | None       = None


BlockRole = Literal["intro", "body", "supporting", "cta", "closing"]
BlockTone = Literal["informational", "review", "story", "promotional"]


# ---------------------------------------------------------------------------
# Block hierarchy — 7 types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HeadingBlock:
    """H1–H6 제목 블록."""
    level: Literal[1, 2, 3, 4, 5, 6]
    text:  str


@dataclass(frozen=True)
class ParagraphBlock:
    """
    텍스트 단락 하나.

    AI 프롬프트는 prompt → keyword → (빈 값) 순으로 우선한다.
    keyword 가 있으면 generate_paragraphs() 가 SEO 최적화 프롬프트를 자동 생성한다.

    Attributes:
        prompt:    Gemini 에 직접 전달할 프롬프트.
                   keyword 와 함께 쓰면 keyword 우선 (SEO 자동 프롬프트).
        keyword:   SEO 키워드. 설정 시 위치·빈도·문체를 포함한 프롬프트를 자동 생성.
        tone:      문체. keyword 가 있을 때 프롬프트 생성에 사용.
        min_chars: 최소 글자 수 (0 = 제한 없음).
        max_chars: 최대 글자 수 (0 = 제한 없음).
        newlines:  단락 뒤 줄바꿈 횟수 (기본 2).
    """
    prompt:    str       = ""
    keyword:   str       = ""
    tone:      BlockTone = "informational"
    min_chars: int       = 0
    max_chars: int       = 0
    newlines:  int       = 2


@dataclass(frozen=True)
class ImageBlock:
    """
    본문 이미지 하나. 대표 이미지로 지정되지 않는다.

    Attributes:
        path:               업로드할 이미지 파일 경로.
        alt:                이미지 대체 텍스트.
        link:               이미지 클릭 시 이동할 URL (tel:, http:// 등).
        exif_optimization:  True면 현실적인 카메라 EXIF 자동 삽입.
        pixel_jitter:       1-3 픽셀 RGB 미세 변경.
        size_jitter_px:     ±N px 리사이즈.
        saturation_jitter:  채도 변화 (±, 기본 ±3%).
        exif_description:   Exif ImageDescription 값.
        exif_gps_lat:       Exif GPS 위도.
        exif_gps_lng:       Exif GPS 경도.
        filename_keyword:   업로드 파일명에 포함할 키워드.
    """
    path:               str        = ""
    alt:                str        = ""
    link:               str        = ""
    exif_optimization:  bool       = True
    pixel_jitter:       bool       = True
    size_jitter_px:     int        = 2
    saturation_jitter:  float      = 0.03
    exif_description:   str        = ""
    exif_gps_lat:       float | None = None
    exif_gps_lng:       float | None = None
    filename_keyword:   str        = ""


@dataclass(frozen=True)
class FeaturedImageBlock:
    """
    대표(썸네일) 이미지 하나.
    업로드 후 포스트 대표 이미지로 지정된다.

    Attributes:
        path:                    업로드할 이미지 파일 경로.
        overlay_text:            이미지 위에 렌더링할 텍스트.
                                 str → 공백으로 분리해 줄별 표시.
                                 list[str] → 각 요소가 한 줄.
        overlay_color:           텍스트 색상 (hex, 기본 "#FFFFFF").
        overlay_background:      텍스트 뒤 반투명 배너 불투명도 (0.0~1.0, 기본 0.0=없음).
        overlay_position:        텍스트 위치 ("top", "center", "bottom").
        link:                    이미지 클릭 시 이동할 URL (tel:, http:// 등).
        exif_optimization:       True면 현실적인 카메라 EXIF 자동 삽입.
        pixel_jitter:            1-3 픽셀 RGB 미세 변경.
        size_jitter_px:          ±N px 리사이즈.
        saturation_shift:        채도 변화 (±, 기본 ±30%).
        hue_shift:               색조 회전 (±, 기본 ±3%). 같은 이미지가 다른 톤으로 보임.
        brightness_shift:        밝기 변화 (±, 기본 ±5%).
        exif_description:        Exif ImageDescription 값 (ASCII만).
        exif_gps_lat:            Exif GPS 위도.
        exif_gps_lng:            Exif GPS 경도.
        filename_keyword:        업로드 파일명에 포함할 키워드.
    """
    path:                   str        = ""
    overlay_text:           str | list = ""
    overlay_color:          str        = "#FFFFFF"
    overlay_background:     float      = 0.0
    overlay_position:       str        = "center"
    link:                   str        = ""
    exif_optimization:      bool       = True
    pixel_jitter:           bool       = True
    size_jitter_px:         int        = 2
    saturation_shift:       float      = 0.30
    hue_shift:              float      = 0.03
    brightness_shift:       float      = 0.05
    exif_description:       str        = ""
    exif_gps_lat:           float | None = None
    exif_gps_lng:           float | None = None
    filename_keyword:       str        = ""


@dataclass(frozen=True)
class ListBlock:
    """순서 있는/없는 목록 블록."""
    items:   tuple[str, ...]  = field(default_factory=tuple)
    ordered: bool             = False


@dataclass(frozen=True)
class QuoteBlock:
    """인용문 블록."""
    text:        str      = ""
    attribution: str      = ""


@dataclass(frozen=True)
class DividerBlock:
    """구분선 블록. 내용 없음."""


# Sealed union — isinstance 분기에 사용
Block = Union[
    HeadingBlock,
    ParagraphBlock,
    ImageBlock,
    FeaturedImageBlock,
    ListBlock,
    QuoteBlock,
    DividerBlock,
]


# ---------------------------------------------------------------------------
# Section — Block 의 컨테이너
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Section:
    """
    의미 단위 컨테이너. 모든 Block 은 반드시 Section 안에 있어야 한다.

    Attributes:
        blocks: 이 섹션에 속한 Block 목록. 순서가 곧 레이아웃이다.
        role:   섹션의 역할.
        tone:   섹션의 문체.
    """
    blocks: tuple[Block, ...] = field(default_factory=tuple)
    role:   BlockRole         = "body"
    tone:   BlockTone         = "informational"


# ---------------------------------------------------------------------------
# PublishOption
# ---------------------------------------------------------------------------

ScheduleMode  = Literal["immediate", "scheduled"]
TagStyle      = Literal["dynamic", "education", "region", "subject", "learning_type"]
Visibility    = Literal["public", "private", "draft"]


@dataclass(frozen=True)
class PublishOption:
    """
    발행에 관한 모든 결정을 담는다.

    Schedule
    --------
    mode="immediate"   즉시 발행 (기본값).
    mode="scheduled"   at 시각에 예약. at 은 항상 미래, timezone-aware.
    """
    # ── Schedule ──────────────────────────────────────────────────────────────
    mode:           ScheduleMode    = "immediate"
    at:             datetime | None = None

    # ── Tags ──────────────────────────────────────────────────────────────────
    tags:                list[str]  = field(default_factory=list)
    min_tags:            int        = 12
    max_tags:            int        = 20
    tag_style:           TagStyle   = "dynamic"
    backlink_ratio:      int        = 0
    internal_link_ratio: int        = 0

    # ── Visibility ────────────────────────────────────────────────────────────
    visibility: Visibility = "public"


# ---------------------------------------------------------------------------
# RunSetting
# ---------------------------------------------------------------------------

OnFailure = Literal["stop", "switch_account"]


@dataclass(frozen=True)
class RunSetting:
    """Runtime behaviour: throttling, failure handling, browser."""
    scheduled:         bool      = True
    schedule_interval: int       = 12
    post_interval:     int       = 60
    max_daily_posts:   int       = 10
    on_failure:        OnFailure = "stop"
    headless:          bool      = True
    slow_mo:           int       = 0
    upload_delay_ms:   int       = 1500   # 이미지 업로드 간 대기 (ms)
