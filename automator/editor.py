"""
automator/editor.py
-------------------
Abstract interface for a blog editor.

NaverBlogJob depends only on this interface — it has no knowledge of DOM,
CSS selectors, iframes, or any other front-end implementation detail.

If Naver replaces Smart Editor One with a different editor, only the
concrete implementation (smart_editor.py) needs to change. The job layer
and all job-level tests remain untouched.

Contract
--------
All methods are synchronous and raise on failure. Callers (NaverBlogJob)
do not need to handle partial-success states — any exception means the
operation failed and the job should abort.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Value objects — pure data, no Playwright dependency
# ---------------------------------------------------------------------------

@dataclass
class PostContent:
    """
    All content needed to publish a single blog post.

    Attributes:
        title:                Text for the post title field.
        body:                 Text for the post body field.
        images:               Ordered list of local image file paths to upload.
        representative_image: Index into ``images`` to use as the thumbnail.
                              None means no representative image is set.
        tags:                 List of tag strings (not yet wired to the editor).
    """
    title:                str
    body:                 str
    images:               list[str]        = field(default_factory=list)
    representative_image: int | None       = None
    tags:                 list[str]        = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract editor interface
# ---------------------------------------------------------------------------

class BlogEditor(ABC):
    """
    Abstract interface for interacting with a blog post editor.

    Concrete implementations (e.g. SmartEditorOne) translate each method
    into the appropriate DOM interactions. NaverBlogJob calls only these
    methods and never touches Playwright directly.
    """

    @abstractmethod
    def open(self) -> None:
        """
        Navigate to the editor page and wait until it is ready for input.
        Dismisses any blocking overlays (recovery popups, help panels).
        """

    @abstractmethod
    def write_title(self, title: str) -> None:
        """Type ``title`` into the title field."""

    @abstractmethod
    def write_body(self, body: str) -> None:
        """Type ``body`` into the body field."""

    @abstractmethod
    def upload_image(self, image_path: str) -> None:
        """
        Upload the image at ``image_path`` via the editor toolbar.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist on disk.
        """

    @abstractmethod
    def set_representative_image(self, index: int) -> None:
        """
        Mark the image at ``index`` (0-based) as the post thumbnail.

        Raises:
            ValueError:   If ``index`` is negative.
            RuntimeError: If the editor does not confirm the selection.
        """

    @abstractmethod
    def move_cursor_to_end(self) -> None:
        """
        Move the editor cursor to the end of the document.

        Call this between consecutive image uploads to ensure each image
        is appended as a new block rather than inserted at the same position.
        """

    @abstractmethod
    def publish(self) -> None:
        """
        Open the publish popover and confirm publication.

        After this call returns the post is live.
        """
