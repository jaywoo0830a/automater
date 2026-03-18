"""
automator/options.py
---------------------
Value objects describing a blog posting job.

Design
------
블로그 포스팅 = 5가지 질문의 답:

  AccountOption  — 누가 올리는가
  TitleOption    — 무슨 제목인가
  Block 목록     — 무엇이 담겼는가  (순서 = 레이아웃)
  MediaOption    — 미디어를 어떻게 처리하는가
  PublishOption  — 언제·어떻게 올리는가

Block hierarchy:
  Block = TextBlock | ImageBlock | FeaturedBlock
  TextBlock     → 단락 텍스트  (ParagraphStep 으로 변환)
  ImageBlock    → 본문 이미지  (ImageStep 으로 변환)
  FeaturedBlock → 대표 이미지  (ThumbnailStep 으로 변환)

All dataclasses are frozen (immutable). No I/O. No imports beyond stdlib.
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
        return self.session_path or f"{self.username}_session.json"


# ---------------------------------------------------------------------------
# TitleOption
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TitleOption:
    """
    Rules for generating a post title.

    Template format
    ---------------
    Python str.format()-style {slug} tokens.
    {salt} → random salt from salts.json.

    Examples:
        TitleOption(
            template="{region} {subject} {salt}",
            values={"region": "강남", "subject": "수학"},
        )
        TitleOption(fixed_title="강남 수학 과외 추천")
    """
    template:         str        = ""
    values:           dict       = field(default_factory=dict)
    salt_preset:      str        = ""
    fixed_title:      str        = ""
    has_space:        bool       = True
    add_affix:        bool       = False
    randomize_chars:  bool       = False
    ai_preset_prompt: str        = ""
    seed:             int | None = None


# ---------------------------------------------------------------------------
# Block hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextBlock:
    """
    본문 단락 하나.

    prompt 가 비어있으면 stub 텍스트(UDHR)를 반환한다.
    SEOOption 이 설정되어 있으면 prompt 보다 우선한다.

    Attributes:
        prompt:   Gemini 에 전달할 프롬프트.
        newlines: 단락 뒤 줄바꿈 횟수 (기본 2).
    """
    prompt:   str = ""
    newlines: int = 2


@dataclass(frozen=True)
class ImageBlock:
    """
    본문 이미지 하나. 대표 이미지로 지정되지 않는다.

    Attributes:
        path: 업로드할 이미지 파일 경로.
    """
    path: str


@dataclass(frozen=True)
class FeaturedBlock:
    """
    대표(썸네일) 이미지 하나.
    업로드 후 포스트 대표 이미지로 지정된다.
    MediaOption.featured_overlay_text 가 있으면 텍스트 오버레이가 적용된다.

    Attributes:
        path: 업로드할 이미지 파일 경로.
    """
    path: str


# Sealed union — isinstance 분기에 사용
Block = Union[TextBlock, ImageBlock, FeaturedBlock]


# ---------------------------------------------------------------------------
# MediaOption
# ---------------------------------------------------------------------------

@dataclass
class MediaOption:
    """
    이미지 변환 파이프라인 규칙. 파일 경로를 모른다.
    모든 이미지(ImageBlock + FeaturedBlock)에 동일하게 적용된다.

    Pipeline
    --------
    ImageBlock    : size_jitter → pixel_jitter → saturation(±preview%) → exif
    FeaturedBlock : size_jitter → pixel_jitter → saturation(±featured%) →
                    featured_overlay_text → exif

    Attributes:
        upload_delay_ms:           업로드 간 대기 (ms).
        pixel_jitter:              1-3 픽셀 RGB 미세 변경.
        size_jitter_px:            ±N px 리사이즈.
        preview_saturation_jitter: 본문 이미지 채도 변화 (±%, 기본 ±3%).
        featured_saturation_shift: 대표 이미지 채도 변화 (±%, 기본 ±30%).
        featured_overlay_text:     대표 이미지에 렌더링할 텍스트.
                                   str → 공백으로 분리해 줄별 표시.
                                   list[str] → 각 요소가 한 줄.
        featured_text_color:       텍스트 색상 (hex, 기본 "#FFFFFF").
        featured_line_spacing:     줄 간격 (px).
        featured_letter_spacing:   자간 (px).
        exif_description:          Exif ImageDescription 값.
        exif_gps_lat/lng:          Exif GPS 좌표.
        filename_keyword:          업로드 파일명에 포함할 키워드.
    """
    upload_delay_ms:            int         = 1500
    pixel_jitter:               bool        = True
    size_jitter_px:             int         = 2
    preview_saturation_jitter:  float       = 0.03
    featured_saturation_shift:  float       = 0.30
    featured_overlay_text:      str | list  = ""
    featured_text_color:        str         = "#FFFFFF"
    featured_line_spacing:      int         = 24
    featured_letter_spacing:    int         = 3
    exif_description:           str         = ""
    exif_gps_lat:               float | None = None
    exif_gps_lng:               float | None = None
    filename_keyword:           str         = ""

    def __post_init__(self) -> None:
        if self.upload_delay_ms < 0:
            raise ValueError(f"upload_delay_ms must be ≥ 0, got {self.upload_delay_ms}")
        if self.size_jitter_px < 0:
            raise ValueError(f"size_jitter_px must be ≥ 0, got {self.size_jitter_px}")
        if not (0.0 <= self.preview_saturation_jitter <= 1.0):
            raise ValueError("preview_saturation_jitter must be 0.0–1.0")
        if not (0.0 <= self.featured_saturation_shift <= 1.0):
            raise ValueError("featured_saturation_shift must be 0.0–1.0")
        if not self.featured_text_color.startswith("#") or \
                len(self.featured_text_color) not in (4, 7):
            raise ValueError(
                f"featured_text_color must be hex like '#FFFFFF', "
                f"got {self.featured_text_color!r}"
            )
        if self.featured_line_spacing < 0:
            raise ValueError("featured_line_spacing must be ≥ 0")
        if self.featured_letter_spacing < 0:
            raise ValueError("featured_letter_spacing must be ≥ 0")


# ---------------------------------------------------------------------------
# PublishOption
# ---------------------------------------------------------------------------

ScheduleMode  = Literal["immediate", "fixed", "random_window"]
TagStyle      = Literal["dynamic", "education", "region", "subject", "learning_type"]
Visibility    = Literal["public", "private", "draft"]


@dataclass(frozen=True)
class PublishOption:
    """
    발행에 관한 모든 결정을 담는다.

    일정·태그·공개범위는 "이 포스트를 어떻게 세상에 내놓는가"라는
    같은 이유로 변경된다. 하나의 옵션 클래스로 통합한다.

    Schedule
    --------
    mode="immediate"     즉시 발행 (기본값).
    mode="fixed"         at 시각에 정확히 예약.
    mode="random_window" at ± jitter_minutes 범위 내 무작위 예약.
    at 은 항상 timezone-aware datetime 이어야 한다. (권장: KST)

    Tags
    ----
    tags 가 비어있으면 자동 생성(tag_style 기반).
    명시적으로 지정하면 그대로 사용한다.

    Visibility
    ----------
    "public"  — 전체 공개 (기본값).
    "private" — 비공개.
    "draft"   — 임시저장.
    """
    # ── Schedule ──────────────────────────────────────────────────────────────
    mode:           ScheduleMode    = "immediate"
    at:             datetime | None = None
    jitter_minutes: int             = 30

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
# SEOOption
# ---------------------------------------------------------------------------

VALID_KEYWORD_POSITIONS = ("first_sentence", "early", "anywhere")
VALID_TONES             = ("formal", "informal_friendly", "review_style")


@dataclass
class SEOOption:
    """
    단락별 SEO 최적화 규칙.

    with_seo() 로 설정 시 TextBlock.prompt 보다 우선하며,
    단락 위치(첫/중간/마지막)마다 다른 Gemini 프롬프트를 생성한다.
    """
    keyword:               str       = ""
    keyword_count_first:   int       = 3
    keyword_count_others:  int       = 1
    keyword_count_last:    int       = 2
    keyword_position:      str       = "first_sentence"
    allow_variants:        bool      = True
    related_keywords:      list[str] = field(default_factory=list)
    repeat_title_keyword:  bool      = True
    first_para_min:         int      = 250
    first_para_max:         int      = 400
    other_para_min:         int      = 150
    other_para_max:         int      = 350
    total_min:              int      = 800
    total_max:              int      = 1200
    sentences_per_para_min: int      = 3
    sentences_per_para_max: int      = 7
    sentence_max_chars:     int      = 60
    sentence_variety:       bool     = True
    first_sentence_max:     int      = 40
    include_question:       bool     = True
    tone:                   str      = "review_style"
    include_numbers:        bool     = True
    include_empathy:        bool     = True
    include_cta:            bool     = True
    use_connectors:         bool     = True

    def __post_init__(self) -> None:
        if self.keyword_position not in VALID_KEYWORD_POSITIONS:
            raise ValueError(
                f"keyword_position must be one of {VALID_KEYWORD_POSITIONS}, "
                f"got {self.keyword_position!r}"
            )
        if self.tone not in VALID_TONES:
            raise ValueError(
                f"tone must be one of {VALID_TONES}, got {self.tone!r}"
            )
        for lo, hi, name in (
            (self.first_para_min, self.first_para_max, "first_para"),
            (self.other_para_min, self.other_para_max, "other_para"),
            (self.total_min, self.total_max, "total"),
            (self.sentences_per_para_min, self.sentences_per_para_max, "sentences_per_para"),
        ):
            if lo > hi:
                raise ValueError(f"{name}_min must be ≤ {name}_max")
        for fn in ("keyword_count_first", "keyword_count_others", "keyword_count_last"):
            if getattr(self, fn) < 0:
                raise ValueError(f"{fn} must be ≥ 0")


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
