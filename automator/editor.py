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
        title:                Final title string.
        body:                 Final body string.
        images:               Ordered image paths to upload.
        representative_image: Index into images to set as thumbnail.
                              None = do not set a thumbnail.
        tags:                 List of tag strings.
    """
    title:                str
    body:                 str
    images:               list[str]  = field(default_factory=list)
    representative_image: int | None = None
    tags:                 list[str]  = field(default_factory=list)


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
    def write_body(self, body: str) -> None:
        """Type ``body`` into the body field."""

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
    def publish(self) -> None:
        """Open the publish popover and confirm. Post is live after this."""
