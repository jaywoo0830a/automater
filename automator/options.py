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
        proxies:      Proxy addresses ("ip:port") to cycle through.
        session_path: Path to Playwright storage-state JSON.
                      Defaults to "<naver_id>_session.json".
    """
    naver_id:     str
    naver_pw:     str
    blog_id:      str
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
    headless:          bool      = True
    slow_mo:           int       = 0


# ---------------------------------------------------------------------------
# SEOOption
# ---------------------------------------------------------------------------

VALID_KEYWORD_POSITIONS = ("first_sentence", "early", "anywhere")
VALID_TONES             = ("formal", "informal_friendly", "review_style")


@dataclass
class SEOOption:
    """
    Controls how Gemini generates paragraph text for SEO purposes.

    Passed to seo_prompt.to_prompt(seo, paragraph_index, total_paragraphs)
    which converts it into a structured instruction string for the Gemini API.

    Keyword
    -------
    keyword:
        Primary target keyword (e.g. "강남 수학 과외").
    keyword_count_first:
        How many times the keyword appears in the first paragraph. (2–3 is safe)
    keyword_count_others:
        Per-paragraph keyword count for middle paragraphs.
    keyword_count_last:
        Keyword count for the last paragraph. Naver weights first/last paragraphs heavily.
    keyword_position:
        Where in the first paragraph the keyword first appears.
        "first_sentence" / "early" (first 30%) / "anywhere"
    allow_variants:
        If True, Gemini may mix spacing variants ("강남수학과외" / "강남 수학 과외").
        Reduces spam-detection risk.
    related_keywords:
        Supporting keywords to weave in naturally (e.g. ["대치동", "내신"]).
        Boosts topic-relevance score.
    repeat_title_keyword:
        If True, the post title keyword should appear verbatim in the body.
        Improves title-body keyword match score.

    Character count
    ---------------
    first_para_min / first_para_max:
        Character range for the first paragraph.
    other_para_min / other_para_max:
        Character range for each middle paragraph.
    total_min / total_max:
        Combined character range across all paragraphs.
    sentences_per_para_min / sentences_per_para_max:
        Sentence count range per paragraph.
    sentence_max_chars:
        Maximum characters per sentence. Keep ≤60 for mobile readability.
    sentence_variety:
        If True, mix short (~20 chars) and long (~60 chars) sentences for rhythm.

    Sentence structure
    ------------------
    first_sentence_max:
        Maximum characters for the very first sentence (shown in search preview).
    include_question:
        Insert one question-form sentence in the first paragraph.
        Boosts reader engagement and dwell time.
    tone:
        "formal" / "informal_friendly" / "review_style"
        review_style = first-person experience narrative — highest trust for parent audience.
    include_numbers:
        Include concrete figures (e.g. "성적 30% 향상", "3개월 만에").
        Numbers increase credibility and CTR.
    include_empathy:
        Add empathy phrases (e.g. "많이 고민하셨죠?").
        Effective for parent-targeted content.
    include_cta:
        Append a call-to-action sentence to the last paragraph
        ("댓글로 물어보세요", "저장해두세요").
        Comments / scraps / likes are direct Naver quality signals.
    use_connectors:
        Use transition words between paragraphs ("그런데", "특히", "그래서").
        Smooth flow reduces bounce rate.
    """

    # ── Keyword ──────────────────────────────────────────────────────────────
    keyword:               str       = ""
    keyword_count_first:   int       = 3
    keyword_count_others:  int       = 1
    keyword_count_last:    int       = 2
    keyword_position:      str       = "first_sentence"
    allow_variants:        bool      = True
    related_keywords:      list[str] = field(default_factory=list)
    repeat_title_keyword:  bool      = True

    # ── Character count ───────────────────────────────────────────────────────
    first_para_min:        int       = 250
    first_para_max:        int       = 400
    other_para_min:        int       = 150
    other_para_max:        int       = 350
    total_min:             int       = 800
    total_max:             int       = 1200
    sentences_per_para_min: int      = 3
    sentences_per_para_max: int      = 7
    sentence_max_chars:    int       = 60
    sentence_variety:      bool      = True

    # ── Sentence structure ────────────────────────────────────────────────────
    first_sentence_max:    int       = 40
    include_question:      bool      = True
    tone:                  str       = "review_style"
    include_numbers:       bool      = True
    include_empathy:       bool      = True
    include_cta:           bool      = True
    use_connectors:        bool      = True

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
        if self.first_para_min > self.first_para_max:
            raise ValueError(
                f"first_para_min ({self.first_para_min}) must be ≤ "
                f"first_para_max ({self.first_para_max})"
            )
        if self.other_para_min > self.other_para_max:
            raise ValueError(
                f"other_para_min ({self.other_para_min}) must be ≤ "
                f"other_para_max ({self.other_para_max})"
            )
        if self.total_min > self.total_max:
            raise ValueError(
                f"total_min ({self.total_min}) must be ≤ total_max ({self.total_max})"
            )
        if self.sentences_per_para_min > self.sentences_per_para_max:
            raise ValueError(
                f"sentences_per_para_min ({self.sentences_per_para_min}) must be ≤ "
                f"sentences_per_para_max ({self.sentences_per_para_max})"
            )
        for field_name in ("keyword_count_first", "keyword_count_others", "keyword_count_last"):
            val = getattr(self, field_name)
            if val < 0:
                raise ValueError(f"keyword_count fields must be ≥ 0, got {field_name}={val}")


# ---------------------------------------------------------------------------
# ImageOption
# ---------------------------------------------------------------------------

@dataclass
class ImageOption:
    """
    Controls image processing before upload.

    Each image goes through: pixel_jitter → size_jitter → exif → save.
    Thumbnails additionally go through: thumbnail_text overlay.

    Fields
    ------
    upload_delay_ms:
        Milliseconds to wait after each file upload.
        Prevents Naver editor from failing on rapid sequential uploads.

    pixel_jitter:
        If True, randomly alter 1–3 pixels so the image hash differs
        from the source. Prevents duplicate-content detection.

    size_jitter_px:
        Randomly resize the image by ±N pixels in each dimension.
        0 = no resize. Works together with pixel_jitter.

    preview_saturation_jitter:
        Randomly shift saturation of preview images by ±value (0.0–1.0).
        Keep small — imperceptible colour shift, changes hash only.
        Default 0.03 (±3%).

    thumbnail_saturation_shift:
        Randomly shift saturation of thumbnail images by ±value (0.0–1.0).
        Keep larger — visible colour tone change per posting.
        Default 0.30 (±30%).

    thumbnail_text:
        Text to overlay on thumbnail images. Accepts:
          str  — split by spaces, each word on its own line.
                 e.g. "강남 수학 과외"  →  3 lines
          list[str]  — each element is one line.
                 e.g. ["강남", "수학 과외"]  →  2 lines
        Empty string or empty list = no overlay.

    thumbnail_text_color:
        Hex color for the thumbnail text overlay (e.g. "#FFFFFF").

    thumbnail_line_spacing:
        Pixels between lines. Default 24px — comfortable for Korean
        on a 1000×1000 image with ~150px font size.

    thumbnail_letter_spacing:
        Pixels between characters. Default 3px — subtle spacing for
        Korean syllable blocks which already have internal spacing.

    exif_description:
        Value written to the JPEG Exif ImageDescription field.
        Naver's image crawler reads this. Typically the target keyword.

    exif_gps_lat / exif_gps_lng:
        GPS coordinates embedded in Exif GPS IFD.
        Boosts local search relevance when set to the region's coordinates.
        None = no GPS data.

    filename_keyword:
        Keyword string used when building the upload filename.
        e.g. "강남-수학-과외" → "강남-수학-과외-01.jpg"
        Empty = generic fallback name.
    """

    # ── Upload timing ─────────────────────────────────────────────────────────
    upload_delay_ms:       int   = 1500

    # ── Pixel / size variation ────────────────────────────────────────────────
    pixel_jitter:             bool  = True
    size_jitter_px:           int   = 2
    preview_saturation_jitter:    float = 0.03   # ±3%  — imperceptible
    thumbnail_saturation_shift:   float = 0.30   # ±30% — visible tone change

    # ── Thumbnail text overlay ────────────────────────────────────────────────
    thumbnail_text:           str | list = ""
    thumbnail_text_color:     str   = "#FFFFFF"
    thumbnail_line_spacing:   int   = 24    # px between lines
    thumbnail_letter_spacing: int   = 3     # px between characters

    # ── Exif metadata ─────────────────────────────────────────────────────────
    exif_description:      str         = ""
    exif_gps_lat:          float | None = None
    exif_gps_lng:          float | None = None

    # ── Filename ──────────────────────────────────────────────────────────────
    filename_keyword:      str   = ""

    def __post_init__(self) -> None:
        if self.upload_delay_ms < 0:
            raise ValueError(
                f"upload_delay_ms must be ≥ 0, got {self.upload_delay_ms}"
            )
        if self.size_jitter_px < 0:
            raise ValueError(
                f"size_jitter_px must be ≥ 0, got {self.size_jitter_px}"
            )
        if not (0.0 <= self.preview_saturation_jitter <= 1.0):
            raise ValueError(
                f"preview_saturation_jitter must be 0.0–1.0, "
                f"got {self.preview_saturation_jitter}"
            )
        if not (0.0 <= self.thumbnail_saturation_shift <= 1.0):
            raise ValueError(
                f"thumbnail_saturation_shift must be 0.0–1.0, "
                f"got {self.thumbnail_saturation_shift}"
            )
        if not self.thumbnail_text_color.startswith("#") or \
                len(self.thumbnail_text_color) not in (4, 7):
            raise ValueError(
                f"thumbnail_text_color must be a hex color like '#FFFFFF', "
                f"got {self.thumbnail_text_color!r}"
            )
        if self.thumbnail_line_spacing < 0:
            raise ValueError(
                f"thumbnail_line_spacing must be ≥ 0, got {self.thumbnail_line_spacing}"
            )
        if self.thumbnail_letter_spacing < 0:
            raise ValueError(
                f"thumbnail_letter_spacing must be ≥ 0, got {self.thumbnail_letter_spacing}"
            )
