"""
automator/editor.py
-------------------
BlogEditor ABC (7 primitives) + PostStep ABC (self-executing command).

BlogEditor primitives
---------------------
    open()                          — navigate and wait
    write_title(title)              — title field
    insert_text(text, newlines)     — any text at cursor
    upload_file(path)               — any file via chooser
    move_cursor(position)           — reposition cursor
    set_representative_media(index) — mark thumbnail
    publish(schedule_at)            — publish or schedule

PostStep hierarchy (internal)
-----------------------------
Each step carries data + execute(editor).  No isinstance anywhere.

    ParagraphStep       -> insert_text
    ImageStep           -> upload_file
    FeaturedImageStep   -> upload_file  (marks_representative=True)
    HeadingStep         -> insert_text
    ListStep            -> insert_text
    QuoteStep           -> insert_text
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ---------------------------------------------------------------------------
# Cursor position
# ---------------------------------------------------------------------------

CursorPosition = Literal["end", "start"]


# ---------------------------------------------------------------------------
# BlogEditor ABC — 7 primitives
# ---------------------------------------------------------------------------

class BlogEditor(ABC):
    """
    Blog editor abstraction with type-agnostic primitives.

    insert_text covers paragraphs, headings, quotes, lists.
    upload_file covers images, videos, attachments.
    New block types never require new methods here.
    """

    @abstractmethod
    def open(self) -> None:
        """Navigate to write page and wait for editor to be ready."""

    @abstractmethod
    def write_title(self, title: str) -> None:
        """Type title into the title field."""

    @abstractmethod
    def insert_text(self, text: str, newlines: int = 2) -> None:
        """Insert text at the current cursor position."""

    @abstractmethod
    def insert_heading(self, text: str, level: int = 2) -> None:
        """
        Insert a heading with editor-native formatting.

        Args:
            text:  Heading text.
            level: Heading level (2=소제목 in Naver, platform-specific).
        """

    @abstractmethod
    def insert_quote(self, text: str) -> None:
        """
        Insert a quote block with editor-native formatting.

        Args:
            text: Quote text.
        """

    @abstractmethod
    def insert_divider(self) -> None:
        """Insert a horizontal divider with editor-native formatting."""

    @abstractmethod
    def upload_file(self, path: str) -> None:
        """Upload a file via the file chooser dialog."""

    @abstractmethod
    def move_cursor(self, position: CursorPosition = "end") -> None:
        """Reposition the cursor."""

    @abstractmethod
    def set_representative_media(self, index: int) -> None:
        """
        Set the index-th (0-based) uploaded image as representative.

        Raises:
            ValueError:   index is negative.
            RuntimeError: editor cannot confirm the selection.
        """

    @abstractmethod
    def publish(self, schedule_at: datetime | None = None) -> None:
        """Publish the post, or schedule it at the given KST datetime."""


# ---------------------------------------------------------------------------
# PostStep ABC — self-executing command
# ---------------------------------------------------------------------------

class PostStep(ABC):
    """
    Abstract command that knows how to execute itself on a BlogEditor.

    Orchestration properties:
        needs_upload_delay   — True for file uploads
        marks_representative — True for featured image uploads
    """

    @abstractmethod
    def execute(self, editor: BlogEditor) -> None:
        """Execute this step on the given editor."""

    @property
    def needs_upload_delay(self) -> bool:
        return False

    @property
    def marks_representative(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Concrete steps
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParagraphStep(PostStep):
    """Insert a paragraph of text."""
    text:     str
    newlines: int = 2

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_text(self.text, self.newlines)


@dataclass(frozen=True)
class ImageStep(PostStep):
    """Upload a body image."""
    path: str
    link: str = ""

    def execute(self, editor: BlogEditor) -> None:
        editor.upload_file(self.path)

    @property
    def needs_upload_delay(self) -> bool:
        return True


@dataclass(frozen=True)
class FeaturedImageStep(PostStep):
    """Upload a featured image (marked as representative)."""
    path: str
    link: str = ""

    def execute(self, editor: BlogEditor) -> None:
        editor.upload_file(self.path)

    @property
    def needs_upload_delay(self) -> bool:
        return True

    @property
    def marks_representative(self) -> bool:
        return True


@dataclass(frozen=True)
class HeadingStep(PostStep):
    """Insert a heading with editor-native formatting."""
    level: int
    text:  str

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_heading(self.text, self.level)


@dataclass(frozen=True)
class ListStep(PostStep):
    """Insert a list as formatted text."""
    text: str

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_text(self.text, 2)


@dataclass(frozen=True)
class QuoteStep(PostStep):
    """Insert a quote with editor-native formatting."""
    text: str

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_quote(self.text)


@dataclass(frozen=True)
class DividerStep(PostStep):
    """Insert a horizontal divider."""

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_divider()


# ---------------------------------------------------------------------------
# _PostContent — internal data transfer between generate and execute
# ---------------------------------------------------------------------------

@dataclass
class _PostContent:
    """Internal: ContentBuilder creates, JobRunner._execute consumes."""
    title:       str
    steps:       list[PostStep]  = field(default_factory=list)
    tags:        list[str]       = field(default_factory=list)
    schedule_at: datetime | None = None
    tmp_files:   list[str]       = field(default_factory=list)
