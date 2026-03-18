"""
automator/editor.py
-------------------
Typed post step hierarchy + BlogEditor ABC.

PostStep 계층 (Option B — typed dataclasses)
-------------------------------------------
PostStep = ParagraphStep | ImageStep | ThumbnailStep

각 step 타입이 자신이 필요한 데이터를 명시적으로 보유한다.
BlogEditor.execute(step) 가 isinstance 로 분기하므로
새 step 타입 추가 = 새 dataclass + execute() 분기 추가.
지원하지 않는 step 은 silently skip 처리한다.

BlogEditor ABC
--------------
execute(step) 하나로 모든 콘텐츠 삽입을 추상화한다.
open / write_title / move_cursor_to_end / set_representative_image / publish
는 콘텐츠가 아닌 에디터 상태 제어이므로 별도 메서드로 유지한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Union


# ---------------------------------------------------------------------------
# Typed PostStep hierarchy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParagraphStep:
    """
    본문 단락 텍스트 한 개.

    Attributes:
        text:     삽입할 단락 문자열.
        newlines: 단락 뒤에 추가할 줄바꿈 횟수 (기본 2).
    """
    text:     str
    newlines: int = 2


@dataclass(frozen=True)
class ImageStep:
    """
    본문 이미지 한 장. 대표 이미지로 지정되지 않는다.

    Attributes:
        path: 업로드할 이미지 파일 경로.
    """
    path: str


@dataclass(frozen=True)
class ThumbnailStep:
    """
    대표(썸네일) 이미지 한 장. 업로드 후 대표 이미지로 지정된다.

    Attributes:
        path: 업로드할 이미지 파일 경로.
    """
    path: str


# Union type — isinstance 분기에 사용
PostStep = Union[ParagraphStep, ImageStep, ThumbnailStep]


# ---------------------------------------------------------------------------
# PostContent — 에디터에 전달되는 완성된 포스트
# ---------------------------------------------------------------------------

@dataclass
class PostContent:
    """
    PostingJob 이 생성하고 BlogEditor 가 소비하는 포스트 데이터.

    Attributes:
        title:       최종 제목 문자열.
        steps:       레이아웃 순서대로 정렬된 PostStep 목록.
        tags:        태그 문자열 목록.
        schedule_at: KST-aware datetime (예약 발행) 또는 None (즉시 발행).
    """
    title:       str
    steps:       list[PostStep]  = field(default_factory=list)
    tags:        list[str]       = field(default_factory=list)
    schedule_at: datetime | None = None


# ---------------------------------------------------------------------------
# BlogEditor ABC
# ---------------------------------------------------------------------------

class BlogEditor(ABC):
    """
    블로그 에디터 추상 인터페이스.

    콘텐츠 삽입은 execute(step) 하나로 추상화된다.
    에디터 상태 제어(open, write_title, cursor, rep_image, publish)는
    별도 메서드로 유지한다.

    구현체(SmartEditorOne 등)가 지원하지 않는 PostStep 타입은
    execute() 에서 silently skip 처리하면 된다.
    """

    @abstractmethod
    def open(self) -> None:
        """에디터로 이동하고 입력 가능 상태가 될 때까지 대기한다."""

    @abstractmethod
    def write_title(self, title: str) -> None:
        """제목 필드에 title 을 입력한다."""

    @abstractmethod
    def execute(self, step: PostStep) -> None:
        """
        PostStep 하나를 에디터에 실행한다.

        ParagraphStep → 본문에 텍스트 입력
        ImageStep     → 이미지 업로드 (대표 지정 없음)
        ThumbnailStep → 이미지 업로드 (대표 지정은 PostingJob 이 별도 호출)

        지원하지 않는 step 타입은 silently skip 한다.
        """

    @abstractmethod
    def set_representative_image(self, index: int) -> None:
        """
        index 번째(0-based) 업로드 이미지를 대표 이미지로 지정한다.

        Raises:
            ValueError:   index 가 음수일 때.
            RuntimeError: 에디터가 선택을 확인하지 못할 때.
        """

    @abstractmethod
    def move_cursor_to_end(self) -> None:
        """커서를 문서 끝으로 이동한다 (연속 업로드 전 호출)."""

    @abstractmethod
    def publish(self, schedule_at: datetime | None = None) -> None:
        """
        포스트를 발행한다.

        Args:
            schedule_at: KST-aware datetime (예약) 또는 None (즉시).
        """
