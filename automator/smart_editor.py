"""
automator/smart_editor.py
--------------------------
SmartEditorOne — Naver Smart Editor implementation of BlogEditor.

Dependencies:
    SelectorLoader  — selectors/naver/editor.yaml
    browser_actions — pure DOM functions
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

from automator.editor import BlogEditor, CursorPosition
from automator.options import Alignment, Visibility
from automator.selector_loader import SelectorLoader
from automator.ports import SelectorSource
from automator.browser_actions import (
    click_if_visible,
    dismiss_polling,
    find_editor_frame,
    find_js_frame,
    locator_dispatch_click,
    select_option_by_value,
    wait_until_attached,
)

_EDITOR_JSON = Path("selectors/naver/editor.yaml")
_MAIN_FRAME  = "#mainFrame"
_EDITOR_BODY = ".se-content"


class SmartEditorOne(BlogEditor):
    """
    Naver Smart Editor One implementation of BlogEditor.

    Args:
        page:       An authenticated Playwright Page.
        write_url:  Blog write page URL.
        dry_run:    If True (default), publish() skips confirm.
        sel_source: Optional SelectorSource for dependency injection.
    """

    def __init__(
        self,
        page: Page,
        write_url: str,
        dry_run: bool = True,
        sel_source: SelectorSource | None = None,
    ) -> None:
        super().__init__(dry_run=dry_run)
        self._page       = page
        self._write_url  = write_url
        self._sel_source = sel_source
        self._sel_cache: SelectorLoader | None = None

    # ------------------------------------------------------------------
    # BlogEditor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Navigate to write page and wait for editor to be ready."""
        self._page.goto(self._write_url)
        self._page.wait_for_load_state("domcontentloaded")

        if self._write_url.split("?")[0] in self._page.url:
            self._page.reload(wait_until="domcontentloaded")

        if "nid.naver.com" in self._page.url or "login" in self._page.url.lower():
            raise RuntimeError(
                "Redirected to login page. Session may have expired. "
                f"Current URL: {self._page.url}"
            )

        self._page.frame_locator(_MAIN_FRAME).locator(_EDITOR_BODY).wait_for(
            state="visible", timeout=30_000
        )
        self._wait_for_editor_ready(self._frame(), self._sel())

    _ALIGN_KEY_MAP = {
        "left":   "align_left",
        "center": "align_center",
        "right":  "align_right",
    }

    def set_align(self, align: Alignment) -> None:
        """Ctrl+A → align dropdown → select direction → Escape."""
        frame = self._frame()
        sel   = self._sel()

        self._click_last_paragraph(frame)
        self._page.keyboard.press("Control+a")

        trigger = sel.locator(frame, "align_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self._page.keyboard.press("Escape")
            return

        align_key = self._ALIGN_KEY_MAP.get(align, "align_left")
        click_if_visible(sel.locator(frame, align_key), timeout_ms=3_000)
        self._page.keyboard.press("Escape")

    def write_title(self, title: str) -> None:
        """Click title placeholder and type title."""
        frame = self._frame()
        sel   = self._sel()
        el    = sel.locator(frame, "editor_title")
        el.wait_for(state="visible", timeout=5_000)
        el.click()
        self._page.keyboard.type(title)

    def insert_text(self, text: str, newlines: int = 2) -> None:
        """Click last paragraph and type text."""
        self._click_last_paragraph()

        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line:
                self._page.keyboard.type(line)
            if i < len(lines) - 1:
                self._page.keyboard.press("Enter")

        # Editor DOM lags on long text — wait proportionally.
        if len(text) >= 100:
            time.sleep(min(60, max(2, len(text) // 100)))

        for _ in range(max(newlines, 1)):
            self._page.keyboard.press("Enter")

    _HEADING_SIZE_MAP = {
        1: "size_38", 2: "size_34", 3: "size_30",
        4: "size_28", 5: "size_24", 6: "size_19",
    }

    def insert_heading(self, text: str, level: int = 2) -> None:
        """Insert heading with native Naver subtitle formatting + font size."""
        frame = self._frame()
        sel   = self._sel()

        self._click_last_paragraph(frame)

        trigger = sel.locator(frame, "heading_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self.insert_text(text, 1)
            return

        heading_btn = sel.locator(frame, "heading_button")
        if not click_if_visible(heading_btn, timeout_ms=3_000):
            self.insert_text(text, 1)
            return

        self._page.keyboard.type(text)

        # Select text → change font size
        self._page.keyboard.press("Home")
        self._page.keyboard.press("Shift+End")
        size_key = self._HEADING_SIZE_MAP.get(level, "size_34")
        size_trigger = sel.locator(frame, "size_trigger")
        if click_if_visible(size_trigger, timeout_ms=3_000):
            click_if_visible(sel.locator(frame, size_key), timeout_ms=3_000)

        click_if_visible(sel.locator(frame, "bold_button"), timeout_ms=3_000)

        # Deselect → exit subtitle
        self._click_last_paragraph(frame)
        self._page.keyboard.press("Enter")

    def insert_quote(self, text: str) -> None:
        """Insert quote block with native formatting."""
        frame = self._frame()
        sel   = self._sel()

        self._click_last_paragraph(frame)

        trigger = sel.locator(frame, "quote_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self.insert_text(text, 2)
            return

        quote_btn = sel.locator(frame, "quote_1")
        if not click_if_visible(quote_btn, timeout_ms=3_000):
            self.insert_text(text, 2)
            return

        self._page.keyboard.type(text)
        self._click_editor_bottom(frame)

    def insert_list(self, items: list[str], ordered: bool = False) -> None:
        """Insert list block with native formatting."""
        if not items:
            return

        frame = self._frame()
        sel   = self._sel()

        self._click_last_paragraph(frame)

        trigger = sel.locator(frame, "list_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self.insert_text("\n".join(items), 2)
            return

        list_btn = sel.locator(frame, "list_type_1")
        if not click_if_visible(list_btn, timeout_ms=3_000):
            self.insert_text("\n".join(items), 2)
            return

        for i, item in enumerate(items):
            self._page.keyboard.type(item)
            if i < len(items) - 1:
                self._page.keyboard.press("Enter")

        # Enter 3x to exit list block
        for _ in range(3):
            self._page.keyboard.press("Enter")

    def insert_divider(self) -> None:
        """Insert horizontal divider with native formatting."""
        frame = self._frame()
        sel   = self._sel()

        self._click_last_paragraph(frame)

        trigger = sel.locator(frame, "divider_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            return

        divider_btn = sel.locator(frame, "divider_2")
        if not click_if_visible(divider_btn, timeout_ms=3_000):
            return

        self._click_editor_bottom(frame)

    def upload_file(self, path: str) -> None:
        """Upload a file via toolbar button."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path!r}")

        frame = self._frame()
        sel   = self._sel()

        trigger = sel.locator(frame, "toolbar_image")
        trigger.wait_for(state="visible", timeout=10_000)

        with self._page.expect_file_chooser() as fc_info:
            trigger.click()
        fc_info.value.set_files(str(path))

        dismiss_polling(
            locator    = sel.locator(frame, "library_close").first,
            timeout_ms = 5_000,
        )

        sel.locator(frame, "editor_image").last.wait_for(
            state="visible", timeout=10_000
        )

    def insert_link(self, url: str) -> None:
        """Attach a hyperlink to the last uploaded image."""
        if not url:
            return

        frame = self._frame()
        sel   = self._sel()

        image_block = sel.locator(frame, "editor_image_block").last
        image_block.wait_for(state="visible", timeout=5_000)
        image_block.click()

        link_btn = sel.locator(frame, "editor_link_button")
        if not click_if_visible(link_btn, timeout_ms=3_000):
            return

        link_input = sel.locator(frame, "editor_link_input")
        link_input.wait_for(state="visible", timeout=3_000)
        link_input.fill(url)

        confirm_btn = sel.locator(frame, "editor_link_confirm")
        if not click_if_visible(confirm_btn, timeout_ms=3_000):
            return

        self._click_last_paragraph(frame)

    def set_representative_media(self, index: int) -> None:
        """Set representative (thumbnail) image by insertion index.

        After selecting the rep image, the image component remains
        selected — its overlay (.se-selection, .se-floating-material-container)
        blocks all keyboard input to the text area.

        To escape, click ``div.se-canvas-bottom`` ("본문 추가" area) which
        deselects the image and moves the cursor to a fresh paragraph.
        Verified in tests/e2e/test_debug_rep_media.py.
        """
        if index < 0:
            raise ValueError(f"index must be >= 0, got {index}")

        frame = self._frame()
        sel   = self._sel()

        block = sel.locator(frame, "editor_image_block").nth(index)
        block.wait_for(state="visible", timeout=5_000)
        block.hover()

        result = locator_dispatch_click(
            sel.locator(frame, "editor_image_rep"),
            index=index,
        )
        if result != "selected":
            raise RuntimeError(
                f"set_representative_media(index={index}) failed: "
                f"JS returned {result!r}"
            )

        wait_until_attached(
            sel.locator(frame, "editor_image_rep_selected").first,
            timeout_ms=5_000,
        )

        # 이미지 선택 오버레이 탈출 — 캔버스 하단 "본문 추가" 영역 클릭
        sel.locator(frame, "editor_canvas_bottom").first.click()

    def move_cursor(self, position: CursorPosition = "end") -> None:
        """Reposition cursor via keyboard (no clicking)."""
        self._page.keyboard.press("Escape")
        key = "Control+Home" if position == "start" else "Control+End"
        self._page.keyboard.press(key)

    def schedule(self, at: datetime) -> None:
        """Open publish popover and set scheduled time."""
        self._click_publish_trigger()
        self._wait_for_popover_ready()
        self._set_scheduled_publish(at)

    _VISIBILITY_LABEL_MAP = {
        "public":  "전체공개",
        "private": "비공개",
    }

    def set_visibility(self, visibility: Visibility) -> None:
        """Set post visibility via JS click (labels lack ARIA role)."""
        self._click_publish_trigger()

        label_text = self._VISIBILITY_LABEL_MAP.get(visibility, "전체공개")
        js_frame = find_js_frame(self._page, url_fragment="PostWriteForm")
        js_frame.evaluate(
            """(text) => {
                const labels = document.querySelectorAll('label');
                for (const label of labels) {
                    if (label.textContent.trim() === text) {
                        label.click();
                        return;
                    }
                }
            }""",
            label_text,
        )

    def insert_tags(self, tags: list[str]) -> None:
        """Type tags in the publish popover (Space to confirm each)."""
        if not tags:
            return

        self._click_publish_trigger()

        sel   = self._sel()
        frame = self._popover_frame()

        tag_input = sel.locator(frame, "tag_textarea")
        if not click_if_visible(tag_input, timeout_ms=3_000):
            return

        for tag in tags:
            self._page.keyboard.type(tag)
            self._page.keyboard.press("Space")

    def publish(self) -> None:
        """Open publish popover and confirm (skipped in dry_run)."""
        self._click_publish_trigger()

        if self._dry_run:
            print(
                "[SmartEditorOne] DRY RUN — confirm skipped.",
                file=sys.stderr,
            )
            return

        self._click_publish_confirm()
        self._wait_for_publish_complete()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _click_last_paragraph(self, frame=None) -> None:
        """Click last paragraph (force=True to bypass image overlays)."""
        if frame is None:
            frame = self._frame()
        sel = self._sel()
        target = sel.locator(frame, "editor_paragraph_container").last
        target.wait_for(state="visible", timeout=5_000)
        target.click(force=True)

    def _click_editor_bottom(self, frame) -> None:
        """Click bottom of .se-content to exit quote/list/divider blocks."""
        editor_body = frame.locator(_EDITOR_BODY)
        box = editor_body.bounding_box()
        if box:
            editor_body.click(position={
                "x": box["width"] / 2,
                "y": box["height"] - 5,
            })

    def _sel(self) -> SelectorLoader:
        """Return cached SelectorLoader."""
        if self._sel_cache is None:
            if self._sel_source is not None:
                self._sel_cache = self._sel_source.load("editor")
            else:
                self._sel_cache = SelectorLoader.load(_EDITOR_JSON)
        return self._sel_cache

    def _frame(self):
        """Editor content frame."""
        return find_editor_frame(self._page, _MAIN_FRAME, _EDITOR_BODY)

    def _popover_frame(self):
        """Publish popover frame (bypasses .se-content visibility check)."""
        return self._page.frame_locator(_MAIN_FRAME).first

    # ------------------------------------------------------------------
    # Publish helpers
    # ------------------------------------------------------------------

    def _wait_for_editor_ready(
        self,
        frame,
        sel,
        timeout_ms: int    = 20_000,
        stable_streak: int = 3,
        probe_ms: int      = 300,
    ) -> None:
        """Dismiss overlays and wait until the editor is stable."""
        _OVERLAYS = ["overlay_draft_cancel", "overlay_help_close"]
        deadline  = time.monotonic() + timeout_ms / 1_000
        streak    = 0

        while time.monotonic() < deadline:
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

        for k in _OVERLAYS:
            click_if_visible(sel.locator(frame, k).first, timeout_ms=1_000)

    def _wait_for_publish_complete(self, timeout: int = 15_000) -> None:
        """Wait for publish navigation."""
        try:
            self._page.wait_for_url(
                lambda url: "Redirect=Write" not in url,
                timeout=timeout,
            )
        except Exception:
            pass
        time.sleep(1)

    def _wait_for_popover_ready(self, timeout_ms: int = 5_000) -> None:
        """Wait for publish popover to render."""
        frame = self._popover_frame()
        sel   = self._sel()
        try:
            sel.locator(frame, "publish_scheduled").wait_for(
                state="attached", timeout=timeout_ms
            )
        except Exception:
            time.sleep(1.0)

    def _click_publish_trigger(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        for ctx in (self._popover_frame(), self._page):
            if click_if_visible(sel.locator(ctx, "toolbar_publish"), timeout):
                return

    def _click_publish_confirm(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        for ctx in (self._page, self._popover_frame()):
            if click_if_visible(sel.locator(ctx, "publish_confirm"), timeout):
                return

    @staticmethod
    def _round_minute_to_10(minute: int) -> str:
        """Floor minute to nearest 10 (Naver UI step)."""
        return f"{(minute // 10) * 10:02d}"

    def _set_scheduled_publish(self, schedule_at: datetime) -> None:
        """Set scheduled time via JS click (label intercepts pointer events)."""
        hour_str   = f"{schedule_at.hour:02d}"
        minute_str = self._round_minute_to_10(schedule_at.minute)

        js_frame = find_js_frame(self._page, url_fragment="PostWriteForm")
        js_frame.evaluate(
            """() => {
                const el = document.querySelector(
                    'input[name="radio_time"][value="pre"]'
                );
                if (el) el.click();
            }"""
        )

        sel   = self._sel()
        frame = self._popover_frame()
        select_option_by_value(sel.locator(frame, "publish_scheduled_hour"), hour_str)
        select_option_by_value(sel.locator(frame, "publish_scheduled_min"),  minute_str)
