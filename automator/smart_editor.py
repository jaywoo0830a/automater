"""
automator/smart_editor.py
--------------------------
Concrete implementation of BlogEditor for Naver Smart Editor One.

THIS IS THE ONLY FILE THAT KNOWS ABOUT DOM.

All DOM knowledge — CSS selectors, iframe paths, JavaScript evaluation,
overlay dismissal, and Playwright-specific timing — lives here.

The DOM logic is ported directly from blog.py, replacing the procedural
function API with the BlogEditor interface so NaverBlogJob can drive it
without any Playwright imports.

Usage:
    from playwright.sync_api import sync_playwright
    from automator.smart_editor import SmartEditorOne
    from automator.options import AccountOption, RunSetting

    account = AccountOption(naver_id="id", naver_pw="pw", blog_id="blog")
    setting = RunSetting()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=setting.headless)
        ctx     = browser.new_context()
        page    = ctx.new_page()
        editor  = SmartEditorOne(page, account.write_url)
        editor.open()
        editor.write_title("제목")
        editor.write_paragraph("본문 단락")
        editor.publish()
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page

from automator.editor import BlogEditor
from automator.browser import (
    MAIN_FRAME,
    EDITOR_CONTENT,
    UPLOADED_IMAGE,
    IMAGE_COMPONENT,
    REP_IMAGE_BUTTON,
    REP_IMAGE_BUTTON_SELECTED,
    POPUP_CANCEL_BUTTON,
    HELP_CLOSE_BUTTON,
    NaverEditorLocators,
    editor_frame,
    editor_js_frame,
)


class SmartEditorOne(BlogEditor):
    """
    Naver Smart Editor One implementation of BlogEditor.

    All DOM knowledge is contained here. When Naver updates the editor,
    this file is the only one that needs to change.

    Args:
        page:      An authenticated Playwright Page.
        write_url: Blog write page URL (from AccountOption.write_url).
    """

    def __init__(self, page: Page, write_url: str) -> None:
        self._page      = page
        self._write_url = write_url

    # ------------------------------------------------------------------
    # BlogEditor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """
        Navigate to the write page and wait until the editor is ready.

        Dismisses:
          1. Draft-recovery popup (button.se-popup-button-cancel)
          2. Help panel (button.se-help-panel-close-button)
        """
        self._page.goto(self._write_url)
        self._page.wait_for_load_state("domcontentloaded")

        # Detect login redirect — naver redirects to nid.naver.com when session expires
        if "nid.naver.com" in self._page.url or "login" in self._page.url.lower():
            raise RuntimeError(
                "Redirected to login page. Session may have expired. "
                f"Current URL: {self._page.url}"
            )

        frame = editor_frame(self._page)
        if frame is self._page:
            self._page.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=30_000)
        else:
            self._page.frame_locator(MAIN_FRAME) \
                .locator(EDITOR_CONTENT) \
                .wait_for(state="visible", timeout=30_000)

        self._dismiss_overlays(frame)

    def write_title(self, title: str) -> None:
        """Click the title placeholder and type ``title``."""
        frame = editor_frame(self._page)
        el    = NaverEditorLocators.title_area(frame)
        el.wait_for(state="visible", timeout=5_000)
        el.click()
        self._page.keyboard.type(title)

    def write_paragraph(self, text: str, newlines: int = 2) -> None:
        """
        Click the body area and type one paragraph of ``text``.

        After typing, presses Enter ``newlines`` times (default: 2) to create
        a blank-line separation before the next paragraph or image block.
        """
        frame = editor_frame(self._page)
        # Click the last text paragraph to ensure focus is on the contenteditable
        # block (not an image component's inner iframe), then type.
        last_para = frame.locator("p.se-text-paragraph").last
        last_para.wait_for(state="visible", timeout=5_000)
        last_para.click()
        self._page.keyboard.type(text)
        for _ in range(max(newlines, 1)):
            self._page.keyboard.press("Enter")

    def upload_image(self, image_path: str) -> None:
        """
        Upload an image via the toolbar button.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path!r}")

        frame   = editor_frame(self._page)
        trigger = NaverEditorLocators.image_trigger(frame)
        trigger.wait_for(state="visible", timeout=10_000)

        with self._page.expect_file_chooser() as fc_info:
            trigger.click()
        fc_info.value.set_files(str(path))

        # Close media library sidebar if it opens
        self._dismiss_library(frame)

        frame.locator(UPLOADED_IMAGE).first.wait_for(state="visible", timeout=10_000)

    def set_representative_image(self, index: int) -> None:
        """
        Set the thumbnail image using JavaScript dispatchEvent.

        The rep button is hidden by CSS; we bypass visibility via JS and
        verify by checking for the se-is-selected class.

        Raises:
            ValueError:   If ``index`` is negative.
            RuntimeError: If JS click does not produce se-is-selected state.
        """
        if index < 0:
            raise ValueError(f"index must be >= 0, got {index}")

        frame = editor_frame(self._page)
        frame.locator(IMAGE_COMPONENT).nth(index).wait_for(state="visible", timeout=5_000)

        js_frame = editor_js_frame(self._page)
        result   = js_frame.evaluate(
            """([selector, idx]) => {
                const btns = document.querySelectorAll(selector);
                if (idx >= btns.length)
                    return `index ${idx} out of range (${btns.length} buttons)`;
                btns[idx].dispatchEvent(
                    new MouseEvent('click', {bubbles: true, cancelable: true})
                );
                return btns[idx].classList.contains('se-is-selected')
                    ? 'selected' : 'not-selected';
            }""",
            [REP_IMAGE_BUTTON, index],
        )

        if result != "selected":
            raise RuntimeError(
                f"set_representative_image(index={index}) failed: "
                f"JS returned {result!r}"
            )

        frame.locator(REP_IMAGE_BUTTON_SELECTED).first.wait_for(
            state="attached", timeout=5_000
        )

    def move_cursor_to_end(self) -> None:
        """
        Move the editor cursor to the end of the document.

        Clicking .se-content directly can land on an image component's inner
        iframe, trapping focus inside it. Instead we click the last text
        paragraph (p.se-text-paragraph) which is always a plain contenteditable
        block, then press Ctrl+End to jump to the document end.
        """
        frame = editor_frame(self._page)
        last_para = frame.locator("p.se-text-paragraph").last
        last_para.click()
        self._page.keyboard.press("Control+End")

    def publish(self) -> None:
        """Open the publish popover and confirm."""
        self._click_publish_trigger()
        self._click_publish_confirm()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dismiss_overlays(self, frame, timeout_ms: int = 6_000) -> None:
        """
        Dismiss all known blocking overlays in order of priority:
          1. Draft-recovery popup  (button.se-popup-button-cancel)
          2. Help panel            (button.se-help-panel-close-button)

        Each overlay is attempted within ``timeout_ms`` total.
        Failures are silently ignored — the overlay may simply not appear.
        """
        self._dismiss_one(
            frame,
            locator=frame.locator(POPUP_CANCEL_BUTTON).first,
            wait_after=None,
            timeout_ms=timeout_ms,
            poll=True,
        )
        self._dismiss_one(
            frame,
            locator=frame.locator(HELP_CLOSE_BUTTON).first,
            wait_after=frame.locator(".se-help-panel"),
            timeout_ms=5_000,
            poll=False,
        )

    def _dismiss_one(self, frame, locator, wait_after, timeout_ms: int, poll: bool) -> None:
        """
        Click ``locator`` if visible within ``timeout_ms``.

        poll=True: repeatedly probe until deadline (for race-condition popups).
        poll=False: single wait_for attempt.
        After clicking, optionally waits for ``wait_after`` to become hidden.
        """
        if poll:
            probe = 200
            deadline = time.monotonic() + timeout_ms / 1_000
            while time.monotonic() < deadline:
                try:
                    locator.wait_for(state="visible", timeout=probe)
                    locator.click()
                    break
                except Exception:
                    pass
        else:
            try:
                locator.wait_for(state="visible", timeout=timeout_ms)
                locator.click()
                if wait_after is not None:
                    wait_after.wait_for(state="hidden", timeout=3_000)
            except Exception:
                pass

    def _dismiss_library(self, frame) -> None:
        """Close the media library sidebar if it appeared after image upload."""
        try:
            btn = NaverEditorLocators.library_close(frame)
            btn.wait_for(state="visible", timeout=3_000)
            btn.click()
        except Exception:
            pass

    def _click_publish_trigger(self, timeout: int = 5_000) -> None:
        """Click the publish trigger button — page-level first, then iframe."""
        try:
            el = NaverEditorLocators.publish_trigger(self._page)
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return
        except Exception:
            pass

        frame = editor_frame(self._page)
        el    = NaverEditorLocators.publish_trigger(frame)
        el.wait_for(state="visible", timeout=timeout)
        el.click()

    def _click_publish_confirm(self, timeout: int = 5_000) -> None:
        """Click the publish confirm button — page-level first, then iframe."""
        try:
            el = NaverEditorLocators.publish_confirm(self._page)
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return
        except Exception:
            pass

        frame = editor_frame(self._page)
        el    = NaverEditorLocators.publish_confirm(frame)
        el.wait_for(state="visible", timeout=timeout)
        el.click()
