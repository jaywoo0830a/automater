"""
automator/smart_editor.py
--------------------------
Concrete implementation of BlogEditor for Naver Smart Editor One.

THIS IS THE ONLY FILE THAT KNOWS ABOUT DOM.

All CSS selectors, iframe paths, JavaScript evaluation, overlay dismissal,
and Playwright-specific timing are contained here. When Naver updates the
editor, this file is the only one that needs to change.

Usage:
    from playwright.sync_api import sync_playwright
    from automator.smart_editor import SmartEditorOne
    from automator.config import settings

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_context().new_page()
        editor  = SmartEditorOne(page, settings)
        editor.open()
        editor.write_title("제목")
        editor.write_body("본문")
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
    editor_frame,
    editor_js_frame,
)
from automator.selector_loader import SelectorLoader


# ---------------------------------------------------------------------------
# Default selector paths
# ---------------------------------------------------------------------------

_DEFAULT_LOGIN_JSON  = Path("selectors/naver/login.json")
_DEFAULT_EDITOR_JSON = Path("selectors/naver/editor.json")


class SmartEditorOne(BlogEditor):
    """
    Naver Smart Editor One implementation of BlogEditor.

    Encapsulates all DOM knowledge: iframe detection, CSS class names,
    JavaScript workarounds, and overlay dismissal.

    Args:
        page:        An authenticated Playwright Page already navigated to
                     the Naver session domain (cookies present).
        write_url:   Blog write page URL (e.g. from settings.write_url).
        editor_json: Path to the superselect editor selector JSON file.
    """

    def __init__(
        self,
        page:        Page,
        write_url:   str,
        editor_json: str | Path = _DEFAULT_EDITOR_JSON,
    ) -> None:
        self._page        = page
        self._write_url   = write_url
        self._sel         = SelectorLoader.load(editor_json)

    # ------------------------------------------------------------------
    # BlogEditor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """
        Navigate to the write page and wait until the editor is ready.

        Dismisses two overlays that appear on first load:
          1. Draft-recovery popup (button.se-popup-button-cancel)
             — appears with a variable delay; polled for up to 5 s.
          2. Help panel (button.se-help-panel-close-button)
             — intercepts pointer events over the publish button.
        """
        self._page.goto(self._write_url)
        self._page.wait_for_load_state("domcontentloaded")

        frame = editor_frame(self._page)
        if frame is self._page:
            self._page.locator(EDITOR_CONTENT).wait_for(state="visible", timeout=15_000)
        else:
            self._page.frame_locator(MAIN_FRAME) \
                .locator(EDITOR_CONTENT) \
                .wait_for(state="visible", timeout=15_000)

        self._dismiss_recovery_popup(frame)
        self._dismiss_help_panel(frame)

    def write_title(self, title: str) -> None:
        """Click the title placeholder and type ``title``."""
        frame = editor_frame(self._page)
        el    = self._sel.locator(frame, "editor_title")
        el.wait_for(state="visible", timeout=5_000)
        el.click()
        self._page.keyboard.type(title)

    def write_body(self, body: str) -> None:
        """Click the body placeholder and type ``body``."""
        frame = editor_frame(self._page)
        el    = self._sel.locator(frame, "editor_body")
        el.wait_for(state="visible", timeout=5_000)
        el.click()
        self._page.keyboard.type(body)

    def upload_image(self, image_path: str) -> None:
        """
        Upload an image via the toolbar button.

        After file selection, Naver sometimes opens a media library sidebar.
        If it does, it is closed automatically before waiting for the image
        to appear in the editor.

        Raises:
            FileNotFoundError: If ``image_path`` does not exist on disk.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path!r}")

        frame   = editor_frame(self._page)
        trigger = self._sel.locator(frame, "image_trigger")
        trigger.wait_for(state="visible", timeout=10_000)

        with self._page.expect_file_chooser() as fc_info:
            trigger.click()
        fc_info.value.set_files(str(path))

        # Close media library sidebar if it opens
        try:
            close_btn = self._sel.locator(frame, "library_close")
            close_btn.wait_for(state="visible", timeout=3_000)
            close_btn.click()
        except Exception:
            pass

        frame.locator(UPLOADED_IMAGE).first.wait_for(state="visible", timeout=10_000)

    def set_representative_image(self, index: int) -> None:
        """
        Set the thumbnail image using JavaScript dispatchEvent.

        The rep button is hidden by CSS; Playwright's visibility checks
        prevent normal hover/click from working on any button beyond index 0.
        We bypass CSS visibility entirely via JS and verify the result by
        checking for the se-is-selected class.

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
        Move the editor cursor to the document end via Ctrl+End.

        Required between consecutive image uploads — without this the second
        upload may overwrite the first image block instead of appending.
        """
        frame = editor_frame(self._page)
        frame.locator(EDITOR_CONTENT).click()
        self._page.keyboard.press("Control+End")

    def publish(self) -> None:
        """
        Open the publish popover and confirm.

        The 발행 trigger button lives in the page-level toolbar (outside the
        iframe). Tries page-level first; falls back to iframe context if not
        found there.
        """
        self._click_publish_trigger()
        self._click_publish_confirm()

    # ------------------------------------------------------------------
    # Private helpers — overlay dismissal and publish internals
    # ------------------------------------------------------------------

    def _dismiss_recovery_popup(self, frame, timeout_ms: int = 5_000) -> None:
        """
        Poll for the draft-recovery popup and dismiss it if found.

        The popup appears with a variable delay after the editor loads,
        so we probe in short intervals rather than doing a single long wait.
        """
        probe_interval = 200
        deadline = time.monotonic() + timeout_ms / 1_000
        while time.monotonic() < deadline:
            try:
                btn = frame.locator(POPUP_CANCEL_BUTTON).first
                btn.wait_for(state="visible", timeout=probe_interval)
                btn.click()
                break
            except Exception:
                pass

    def _dismiss_help_panel(self, frame) -> None:
        """
        Close the help panel if it is open.

        The panel intercepts pointer events and blocks clicks on the publish
        button. It only appears on first load of a new session.
        """
        try:
            btn = frame.locator(HELP_CLOSE_BUTTON).first
            btn.wait_for(state="visible", timeout=2_000)
            btn.click()
        except Exception:
            pass

    def _click_publish_trigger(self, timeout: int = 5_000) -> None:
        """Click the publish trigger button (page-level first, then iframe)."""
        try:
            el = self._sel.locator(self._page, "publish_trigger")
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return
        except Exception:
            pass

        frame = editor_frame(self._page)
        el    = self._sel.locator(frame, "publish_trigger")
        el.wait_for(state="visible", timeout=timeout)
        el.click()

    def _click_publish_confirm(self, timeout: int = 5_000) -> None:
        """Click the publish confirm button (page-level first, then iframe)."""
        try:
            el = self._sel.locator(self._page, "publish_confirm")
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return
        except Exception:
            pass

        frame = editor_frame(self._page)
        el    = self._sel.locator(frame, "publish_confirm")
        el.wait_for(state="visible", timeout=timeout)
        el.click()
