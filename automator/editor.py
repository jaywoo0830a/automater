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
    insert_link(url)                — attach link to last element
    move_cursor(position)           — reposition cursor
    publish()                       — confirm and publish

PostStep hierarchy (internal)
-----------------------------
Each step carries data + execute(editor).  No isinstance anywhere.

    ParagraphStep       -> insert_text
    ImageStep           -> upload_file
    FeaturedImageStep   -> upload_file + insert_link
    HeadingStep         -> insert_text
    ListStep            -> insert_list
    QuoteStep           -> insert_quote
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from automator.options import Alignment, Visibility


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

    Args:
        dry_run: If True (default), publish() prepares everything but
                 skips the final confirm — the post is never actually published.
    """

    def __init__(self, *, dry_run: bool = True) -> None:
        self._dry_run = dry_run

    @property
    def dry_run(self) -> bool:
        """Whether this editor is in dry-run mode."""
        return self._dry_run

    @abstractmethod
    def open(self) -> None:
        """Navigate to write page and wait for editor to be ready."""

    @abstractmethod
    def write_title(self, title: str) -> None:
        """Type title into the title field."""

    @abstractmethod
    def set_align(self, align: Alignment) -> None:
        """
        Set text alignment for the entire post.

        Args:
            align: "left", "center", or "right".
        """

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
    def insert_quote(self, text: str, quote_type: int = 1) -> None:
        """
        Insert a quote block with editor-native formatting.

        Args:
            text:       Quote text.
            quote_type: Quote style number (1~6, platform-specific). Default 1.
        """

    @abstractmethod
    def insert_list(self, items: list[str], ordered: bool = False) -> None:
        """
        Insert a list with editor-native formatting.

        Args:
            items:   List of item strings.
            ordered: True for numbered list, False for bullet list.
        """

    @abstractmethod
    def insert_divider(self, divider_type: int = 2) -> None:
        """
        Insert a horizontal divider with editor-native formatting.

        Args:
            divider_type: Divider style number (1~8, platform-specific). Default 2.
        """

    @abstractmethod
    def upload_file(self, path: str) -> None:
        """Upload a file via the file chooser dialog."""

    @abstractmethod
    def insert_link(self, url: str) -> None:
        """Attach a hyperlink to the last inserted element (image, text, etc.)."""

    @abstractmethod
    def move_cursor(self, position: CursorPosition = "end") -> None:
        """Reposition the cursor."""

    @abstractmethod
    def set_visibility(self, visibility: Visibility) -> None:
        """
        Set post visibility in the publish popover.

        The popover must already be open.

        Args:
            visibility: "public" or "private".
        """

    @abstractmethod
    def insert_tags(self, tags: list[str]) -> None:
        """
        Insert tags in the publish popover.

        The popover must already be open. Each tag is typed then
        confirmed with a space.

        Args:
            tags: List of tag strings.
        """

    @abstractmethod
    def publish(self) -> None:
        """Confirm and publish the post."""

    def dismiss_overlays(self) -> bool:
        """Probe and dismiss any runtime overlays (optional hook).

        Default implementation is a no-op. Platform-specific editors may
        override this to handle draft-recovery popups, help panels,
        media library dialogs, etc. that can appear mid-execution.

        Called before each PostStep by JobRunner so that transient
        overlays cannot cascade into domino failures.

        Returns:
            True if any overlay was dismissed, False otherwise.
        """
        return False


# ---------------------------------------------------------------------------
# PostStep ABC — self-executing command
# ---------------------------------------------------------------------------

class PostStep(ABC):
    """Abstract command that knows how to execute itself on a BlogEditor.

    Subclasses must define ``wait_ms: int = 0`` field.
    After execute(), the runner should call ``wait()`` to honour the delay.
    """

    @abstractmethod
    def execute(self, editor: BlogEditor) -> None:
        """Execute this step on the given editor."""

    def wait(self) -> None:
        """Block for wait_ms if set. Called by runner after execute()."""
        ms = getattr(self, "wait_ms", 0)
        if ms > 0:
            time.sleep(ms / 1000)


# ---------------------------------------------------------------------------
# Concrete steps
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParagraphStep(PostStep):
    """Insert a paragraph of text."""
    text:     str
    newlines: int = 2
    wait_ms:  int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_text(self.text, self.newlines)


@dataclass(frozen=True)
class ImageStep(PostStep):
    """Upload a body image, optionally attaching a link."""
    path:    str
    link:    str = ""
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.upload_file(self.path)
        if self.link:
            editor.insert_link(self.link)


@dataclass(frozen=True)
class FeaturedImageStep(PostStep):
    """Upload a featured image, optionally attaching a link."""
    path:    str
    link:    str = ""
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.upload_file(self.path)
        if self.link:
            editor.insert_link(self.link)


@dataclass(frozen=True)
class TextStep(PostStep):
    """Insert raw text content (from file). No AI generation."""
    text:    str
    is_html: bool = False
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_text(self.text, 2)


@dataclass(frozen=True)
class HeadingStep(PostStep):
    """Insert a heading with editor-native formatting."""
    level:   int
    text:    str
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_heading(self.text, self.level)


@dataclass(frozen=True)
class ListStep(PostStep):
    """Insert a list with editor-native formatting."""
    items:   tuple[str, ...]
    ordered: bool = False
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_list(list(self.items), self.ordered)


@dataclass(frozen=True)
class QuoteStep(PostStep):
    """Insert a quote with editor-native formatting.

    type: 인용구 스타일 (1~6, 기본 1).
    """
    text:    str
    type:    int = 1
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_quote(self.text, self.type)


@dataclass(frozen=True)
class DividerStep(PostStep):
    """Insert a horizontal divider.

    type: 구분선 스타일 (1~8, 기본 2).
    """
    type:    int = 2
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_divider(self.type)


@dataclass(frozen=True)
class NewLineStep(PostStep):
    """Insert N blank line breaks (Enter presses)."""
    count:   int = 1
    wait_ms: int = 0

    def execute(self, editor: BlogEditor) -> None:
        editor.insert_text("", self.count)


# ---------------------------------------------------------------------------
# _PostContent — internal data transfer between generate and execute
# ---------------------------------------------------------------------------

@dataclass
class _PostContent:
    """Internal: ContentBuilder creates, JobRunner._execute consumes."""
    title:       str
    steps:       list[PostStep]  = field(default_factory=list)
    tags:        list[str]       = field(default_factory=list)
    visibility:  Visibility      = "public"
    schedule_at: datetime | None = None
    align:       Alignment | None = None
    tmp_files:   list[str]       = field(default_factory=list)
