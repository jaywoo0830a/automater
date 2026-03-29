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
        weight:       Distribution weight. Higher = more posts assigned.
                      Default 1. Ratio-based: weight 1 vs 3 → 25% vs 75%.
        min_posts:    Minimum guaranteed posts for this account. 0 = no minimum.
                      Allocated first, before weight distribution.
        max_posts:    Hard cap on posts for this account. 0 = unlimited.
                      Applied after weight distribution.
        proxies:      "ip:port" list to cycle through.
        session_path: Playwright storage-state JSON path.
                      Defaults to "<username>_session.json".
    """
    username:     str
    password:     str
    weight:       int       = 1
    min_posts:    int       = 0
    max_posts:    int       = 0
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
    Rules for generating a post title via template DSL.

    Template DSL
    ------------
    {keyword:slug}  — substituted from ``values[slug]`` (deterministic).
    {pool:slug}     — random choice from ``pools[slug]``.
    plain text      — kept as-is.  Spacing is what you type.

    For a fixed title without template processing, pass a plain str
    as PostingSpec.title instead of a TitleOption.

    Examples::

        TitleOption(
            template="{pool:salt_prefix} {keyword:region} {keyword:subject} 과외 {pool:salt_suffix}",
            values={"region": "강남", "subject": "수학"},
            pools={
                "salt_prefix": ("검증된", "전문"),
                "salt_suffix": ("강력 추천", "즉시 가능"),
            },
        )
    """
    template: str                          = ""
    values:   dict                         = field(default_factory=dict)
    pools:    dict[str, tuple[str, ...]]   = field(default_factory=dict)
    seed:     int | None                   = None


BlockRole = Literal["intro", "body", "supporting", "cta", "closing"]
BlockTone = Literal["informational", "review", "story", "promotional"]


# ---------------------------------------------------------------------------
# Block hierarchy — 7 types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HeadingBlock:
    """H1–H6 제목 블록."""
    level:   Literal[1, 2, 3, 4, 5, 6]
    text:    str
    wait_ms: int = 0


@dataclass(frozen=True)
class ParagraphBlock:
    """
    텍스트 단락 하나.

    Attributes:
        prompt:   AI에 전달할 프롬프트. 완성된 프롬프트 문자열.
                  SEO 프롬프트 조립은 CLI 계층의 책임.
        newlines: 단락 뒤 줄바꿈 횟수 (기본 2).
    """
    prompt:   str = ""
    newlines: int = 2
    wait_ms:  int = 0


@dataclass(frozen=True)
class RegionalEffect:
    """
    영역 지정 이미지 효과.

    Attributes:
        region: 적용 영역.
            "all"           — 전체
            "border:20"     — 테두리 20px
            "border:10%"    — 테두리 (짧은 변 기준 10%)
            "center:60%"    — 중앙 60%
            "top:30%"       — 상단 30%
            "bottom:30%"    — 하단 30%
            "left:30%"      — 좌측 30%
            "right:30%"     — 우측 30%
            "rect:x,y,w,h"  — 절대 좌표 (px)
        effect: 적용 효과.
            "brightness:0.5" — 밝기 (1.0=원본)
            "saturation:1.5" — 채도 (1.0=원본)
            "hue:0.1"        — 색조 회전 (0.0~1.0)
            "blur:5"         — 가우시안 블러 (px)
            "tint:R,G,B[,A]" — 컬러 틴트
            "grayscale"      — 흑백
    """
    region: str = "all"
    effect: str = ""


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
        exif_description:   Exif ImageDescription 값.
        exif_gps_lat:       Exif GPS 위도.
        exif_gps_lng:       Exif GPS 경도.
        filename_keyword:   업로드 파일명에 포함할 키워드.
        effects:            영역 지정 효과 목록. 순서대로 적용.
    """
    path:               str        = ""
    alt:                str        = ""
    link:               str        = ""
    exif_optimization:  bool       = True
    pixel_jitter:       bool       = True
    size_jitter_px:     int        = 2
    exif_description:   str        = ""
    exif_gps_lat:       float | None = None
    exif_gps_lng:       float | None = None
    filename_keyword:   str        = ""
    effects:            list[RegionalEffect] = field(default_factory=list)
    wait_ms:            int        = 0


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
        exif_description:        Exif ImageDescription 값 (ASCII만).
        exif_gps_lat:            Exif GPS 위도.
        exif_gps_lng:            Exif GPS 경도.
        filename_keyword:        업로드 파일명에 포함할 키워드.
        effects:                 영역 지정 효과 목록. 순서대로 적용.
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
    exif_description:       str        = ""
    exif_gps_lat:           float | None = None
    exif_gps_lng:           float | None = None
    filename_keyword:       str        = ""
    effects:                list[RegionalEffect] = field(default_factory=list)
    wait_ms:                int        = 0


@dataclass(frozen=True)
class TextBlock:
    """
    외부 파일 내용을 그대로 삽입하는 블록. AI를 거치지 않는다.

    Attributes:
        file:   읽을 파일 경로. 토큰 치환 후 resolve된 경로.
        format: 파일 내용 해석 방식.
                "plain" (기본) — 줄바꿈 기준으로 <p> 분리.
                "html"         — 파일 내용 그대로 삽입.
    """
    file:    str = ""
    format:  str = "plain"
    wait_ms: int = 0


@dataclass(frozen=True)
class ListBlock:
    """순서 있는/없는 목록 블록."""
    items:   tuple[str, ...]  = field(default_factory=tuple)
    ordered: bool             = False
    wait_ms: int              = 0


@dataclass(frozen=True)
class QuoteBlock:
    """인용문 블록."""
    text:        str = ""
    attribution: str = ""
    wait_ms:     int = 0


@dataclass(frozen=True)
class DividerBlock:
    """구분선 블록. 내용 없음."""
    wait_ms: int = 0


# Sealed union — isinstance 분기에 사용
Block = Union[
    HeadingBlock,
    ParagraphBlock,
    TextBlock,
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

ScheduleMode  = Literal["immediate", "scheduled", "sequential"]
TagStyle      = Literal["dynamic", "education", "region", "subject", "learning_type"]
Visibility    = Literal["public", "private", "draft"]


@dataclass(frozen=True)
class PublishOption:
    """
    발행 메타데이터 — 태그, 공개 범위.

    스케줄(언제 발행할지)은 PostingSpec.schedule_at 으로 분리되었다.
    """
    # ── Tags ──────────────────────────────────────────────────────────────────
    tags:                list[str]  = field(default_factory=list)
    min_tags:            int        = 12
    max_tags:            int        = 20
    tag_style:           TagStyle   = "dynamic"
    backlink_ratio:      int        = 0
    internal_link_ratio: int        = 0

    # ── Visibility ────────────────────────────────────────────────────────────
    visibility: Visibility = "public"


