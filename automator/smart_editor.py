"""
automator/smart_editor.py
--------------------------
Layer 3: Editor Shell

Thin OOP adaptor that implements the BlogEditor ABC.

Responsibilities
----------------
1. Resolve selectors  — SelectorLoader.load(editor.json)
2. Resolve frames     — find_editor_frame / find_js_frame  (browser_actions)
3. Delegate DOM work  — browser_actions pure functions

This class contains no DOM logic of its own. When a test exercises
SmartEditorOne it is really testing the wiring, not the DOM operations.
The DOM operations are tested independently in test_browser_actions.py.

Selector key naming rule: {context}_{element}_{variant?}
  context : overlay | toolbar | editor | library | publish
  See selectors/naver/editor.json for the full catalogue.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

from automator.editor import BlogEditor
from automator.selector_loader import SelectorLoader
from automator.browser_actions import (
    click_if_visible,
    click_polling,
    dismiss_polling,
    find_editor_frame,
    find_js_frame,
    js_dispatch_click,
    locator_dispatch_click,
    wait_until_attached,
)

_EDITOR_JSON = Path("selectors/naver/editor.json")
_MAIN_FRAME  = "#mainFrame"
_EDITOR_BODY = ".se-content"


class SmartEditorOne(BlogEditor):
    """
    Naver Smart Editor One implementation of BlogEditor.

    Resolves selectors from editor.json and delegates all DOM work to
    browser_actions functions. No selector strings are hardcoded here.

    Args:
        page:      An authenticated Playwright Page.
        write_url: Blog write page URL (from AccountOption.write_url).
        dry_run:   If True (default), publish() is a no-op.
    """

    def __init__(self, page: Page, write_url: str, dry_run: bool = True) -> None:
        self._page      = page
        self._write_url = write_url
        self._dry_run   = dry_run

    # ------------------------------------------------------------------
    # BlogEditor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """
        Navigate to write page and wait for editor to be ready.

        Three overlays are polled unconditionally — all treated as
        unpredictably timed. Each is silently skipped when absent.
        """
        self._page.goto(self._write_url)
        self._page.wait_for_load_state("domcontentloaded")

        if "nid.naver.com" in self._page.url or "login" in self._page.url.lower():
            raise RuntimeError(
                "Redirected to login page. Session may have expired. "
                f"Current URL: {self._page.url}"
            )

        frame = self._frame()
        frame.locator(_EDITOR_BODY).wait_for(state="visible", timeout=30_000)

        self._wait_for_editor_ready(frame, self._sel())

    def _wait_for_editor_ready(
        self,
        frame,
        sel,
        timeout_ms: int    = 20_000,
        stable_streak: int = 3,
        probe_ms: int      = 300,
    ) -> None:
        """
        Dismiss overlays and wait until the editor is stable.

        Per cycle: check ALL overlays (not any-short-circuit), click each
        that is visible. Streak increments only when no overlay was clicked
        across the entire cycle. Declares ready after stable_streak clean
        cycles (default 3 × 300ms = 0.9s gap with no overlay).

        Why not any(): any() stops at first True — if draft is clicked, help
        is never checked in the same cycle, so both overlays appearing
        together keep resetting the streak indefinitely.
        """
        _OVERLAYS = ["overlay_draft_cancel", "overlay_help_close"]
        deadline  = time.monotonic() + timeout_ms / 1_000
        streak    = 0

        while time.monotonic() < deadline:
            # Check ALL overlays this cycle — never short-circuit
            clicked_this_cycle = [
                click_if_visible(sel.locator(frame, k).first, timeout_ms=probe_ms)
                for k in _OVERLAYS
            ]

            if any(clicked_this_cycle):
                streak = 0
            else:
                streak += 1

            if streak >= stable_streak:
                try:
                    if sel.locator(frame, "editor_title").is_visible():
                        return
                except Exception:
                    streak = 0

            time.sleep(0.1)

        # Deadline exceeded — one last sweep and continue
        for k in _OVERLAYS:
            click_if_visible(sel.locator(frame, k).first, timeout_ms=1_000)

    def write_title(self, title: str) -> None:
        """Click title placeholder and type title."""
        frame = self._frame()
        sel   = self._sel()
        el    = sel.locator(frame, "editor_title")
        el.wait_for(state="visible", timeout=5_000)
        el.click()
        self._page.keyboard.type(title)

    def write_paragraph(self, text: str, newlines: int = 2) -> None:
        """
        Click the last paragraph container and type text.

        Uses editor_paragraph_container (p.se-text-paragraph).
        Guaranteed to be in the main editor — never inside an image iframe.
        Presses Enter newlines times after typing (default: 2).
        """
        frame     = self._frame()
        sel       = self._sel()
        last_para = sel.locator(frame, "editor_paragraph_container").last
        last_para.wait_for(state="visible", timeout=5_000)
        last_para.click()
        self._page.keyboard.type(text)
        for _ in range(max(newlines, 1)):
            self._page.keyboard.press("Enter")

    def upload_image(self, image_path: str) -> None:
        """
        Upload image via toolbar button.

        Raises FileNotFoundError if image_path does not exist.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path!r}")

        frame = self._frame()
        sel   = self._sel()

        trigger = sel.locator(frame, "toolbar_image")
        trigger.wait_for(state="visible", timeout=10_000)

        with self._page.expect_file_chooser() as fc_info:
            trigger.click()
        fc_info.value.set_files(str(path))

        # Library sidebar appears after upload — poll as it may be slow.
        dismiss_polling(
            locator    = sel.locator(frame, "library_close").first,
            timeout_ms = 5_000,
        )

        sel.locator(frame, "editor_image").last.wait_for(
            state="visible", timeout=10_000
        )

    def set_representative_image(self, index: int) -> None:
        """
        Set representative (thumbnail) image by insertion index.

        The rep button is hidden by CSS hover state — uses js_dispatch_click
        to fire a MouseEvent regardless of visibility.

        Raises:
            ValueError:   If index is negative.
            RuntimeError: If the button does not reach selected state.
        """
        if index < 0:
            raise ValueError(f"index must be >= 0, got {index}")

        frame    = self._frame()
        sel      = self._sel()
        block = sel.locator(frame, "editor_image_block").nth(index)
        block.wait_for(state="visible", timeout=5_000)

        # rep 버튼은 이미지 block에 hover해야 DOM에 나타남.
        # hover 후 locator.evaluate로 dispatchEvent — shadow DOM 통과.
        block.hover()
        result = locator_dispatch_click(
            sel.locator(frame, "editor_image_rep"),
            index=index,
        )

        if result != "selected":
            raise RuntimeError(
                f"set_representative_image(index={index}) failed: "
                f"JS returned {result!r}"
            )

        wait_until_attached(
            sel.locator(frame, "editor_image_rep_selected").first,
            timeout_ms=5_000,
        )

    def move_cursor_to_end(self) -> None:
        """
        Move cursor to end of document.

        Clicks p.se-text-paragraph.last — always in the main editor,
        never inside an image component iframe — then presses Ctrl+End.
        """
        frame = self._frame()
        sel   = self._sel()
        sel.locator(frame, "editor_paragraph_container").last.click()
        self._page.keyboard.press("Control+End")

    def publish(self, schedule_at: datetime | None = None) -> None:
        """
        Open publish popover and confirm. No-op in dry_run mode.

        Args:
            schedule_at: KST-aware datetime for reserved publish, or None for
                         immediate publish. When set, the implementation must
                         interact with Naver's reservation UI before confirming.
                         (reservation UI interaction is a stub — not yet implemented)
        """
        if self._dry_run:
            label = schedule_at.isoformat() if schedule_at else "immediate"
            print(
                f"[SmartEditorOne] DRY RUN — publish() skipped (schedule_at={label})",
                file=sys.stderr,
            )
            return

        if schedule_at is not None:
            # TODO: interact with Naver reservation UI to set schedule_at
            # (stub — falls through to immediate publish for now)
            print(
                f"[SmartEditorOne] WARN — reservation UI not yet implemented "
                f"(schedule_at={schedule_at.isoformat()}). Publishing immediately.",
                file=sys.stderr,
            )

        self._click_publish_trigger()
        self._click_publish_confirm()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sel(self) -> SelectorLoader:
        return SelectorLoader.load(_EDITOR_JSON)

    def _frame(self):
        return find_editor_frame(self._page, _MAIN_FRAME, _EDITOR_BODY)

    def _click_publish_trigger(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        for ctx in (self._page, self._frame()):
            if click_if_visible(sel.locator(ctx, "toolbar_publish"), timeout):
                return

    def _click_publish_confirm(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        for ctx in (self._page, self._frame()):
            if click_if_visible(sel.locator(ctx, "publish_confirm"), timeout):
                return
