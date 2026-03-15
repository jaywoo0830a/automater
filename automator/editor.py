"""
automator/editor.py
-------------------
Abstract interface for a blog editor.

NaverBlogJob depends only on this interface — it has no knowledge of DOM,
CSS selectors, iframes, or any browser implementation detail.

If Naver replaces Smart Editor One with a different editor, only the
concrete implementation (smart_editor.py) needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# PostStep — a single unit of editor action in layout order
# ---------------------------------------------------------------------------

@dataclass
class PostStep:
    """
    One ordered step for the editor to execute.

    kind:
        "paragraph" — write a paragraph of body text
        "image"     — upload an image (not representative)
        "thumbnail" — upload an image and mark it as representative
    value:
        "paragraph" → the paragraph text to write
        "image"     → file path to upload
        "thumbnail" → file path to upload
    """
    kind:  str   # "paragraph" | "image" | "thumbnail"
    value: str   # text or file path


# ---------------------------------------------------------------------------
# PostContent — resolved post ready for the editor
# ---------------------------------------------------------------------------

@dataclass
class PostContent:
    """
    Resolved content ready to be written into the editor.

    Produced by NaverBlogJob._generate_content() from the option objects.
    The editor layer only ever sees this — never raw options.

    Attributes:
        title:       Final title string.
        steps:       Ordered list of PostStep — drives the editor in layout order.
                     Each step is one of: paragraph, image, thumbnail.
        tags:        List of tag strings.
        schedule_at: KST-aware datetime to reserve the post, or None for
                     immediate publish. Resolved from MetaOption by the job;
                     the editor receives a concrete datetime (never a mode string).
    """
    title:              str
    steps:              list[PostStep] = field(default_factory=list)
    tags:               list[str]     = field(default_factory=list)
    paragraph_newlines: int           = 2
    schedule_at:        datetime | None = None


# ---------------------------------------------------------------------------
# BlogEditor ABC
# ---------------------------------------------------------------------------

class BlogEditor(ABC):
    """
    Abstract interface for interacting with a blog post editor.

    Concrete implementations (e.g. SmartEditorOne) translate each method
    into the appropriate DOM interactions. NaverBlogJob calls only these
    methods and never touches Playwright directly.

    All methods are synchronous and raise on failure.
    """

    @abstractmethod
    def open(self) -> None:
        """Navigate to the editor and wait until it is ready for input."""

    @abstractmethod
    def write_title(self, title: str) -> None:
        """Type ``title`` into the title field."""

    @abstractmethod
    def write_paragraph(self, text: str, newlines: int = 2) -> None:
        """
        Append a paragraph of text into the body field.

        Called once per "Paragraph N" step in the layout.
        After typing, presses Enter ``newlines`` times to create separation
        between consecutive paragraphs (default: 2).
        """

    @abstractmethod
    def upload_image(self, image_path: str) -> None:
        """
        Upload the image at ``image_path``.

        Raises:
            FileNotFoundError: If the file does not exist.
        """

    @abstractmethod
    def set_representative_image(self, index: int) -> None:
        """
        Mark image at ``index`` (0-based) as the post thumbnail.

        Raises:
            ValueError:   If ``index`` is negative.
            RuntimeError: If the editor does not confirm the selection.
        """

    @abstractmethod
    def move_cursor_to_end(self) -> None:
        """
        Move the editor cursor to the end of the document.

        Call this between consecutive image uploads so each image is
        appended as a new block.
        """

    @abstractmethod
    def publish(self, schedule_at: datetime | None = None) -> None:
        """
        Finalise and submit the post.

        Args:
            schedule_at: KST-aware datetime to reserve the post, or None to
                         publish immediately. The editor implementation is
                         responsible for interacting with the reservation UI
                         when this is not None.
        """
