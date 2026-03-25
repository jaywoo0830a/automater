"""
automator/smart_editor.py
--------------------------
SmartEditorOne — Naver Smart Editor implementation of BlogEditor.

Implements the 7 BlogEditor primitives:
    open, write_title, insert_text, upload_file,
    move_cursor, set_representative_media, publish

Dependencies:
    SelectorLoader  — selectors/naver/editor.json
    browser_actions — pure DOM functions
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page

from automator.editor import BlogEditor, CursorPosition
from automator.selector_loader import SelectorLoader
from automator.ports import SelectorSource
from automator.browser_actions import (
    click_if_visible,
    click_polling,
    dismiss_polling,
    find_editor_frame,
    find_js_frame,
    hover_if_visible,
    js_dispatch_click,
    locator_dispatch_click,
    select_option_by_value,
    wait_until_attached,
)

_EDITOR_JSON = Path("selectors/naver/editor.json")
_MAIN_FRAME  = "#mainFrame"
_EDITOR_BODY = ".se-content"


class SmartEditorOne(BlogEditor):
    """
    Naver Smart Editor One implementation of BlogEditor.

    Resolves selectors via an injected SelectorSource (or falls back to
    loading editor.json directly). Delegates all DOM work to
    browser_actions functions. No selector strings are hardcoded here.

    Args:
        page:       An authenticated Playwright Page.
        write_url:  Blog write page URL (e.g. from account.meta['blog_id']).
        dry_run:    If True (default), publish() is a no-op.
        sel_source: Optional SelectorSource for dependency injection.
                    When None, loads selectors/naver/editor.json directly.
    """

    def __init__(
        self,
        page: Page,
        write_url: str,
        dry_run: bool = True,
        sel_source: SelectorSource | None = None,
    ) -> None:
        self._page       = page
        self._write_url  = write_url
        self._dry_run    = dry_run
        self._sel_source = sel_source
        self._sel_cache: SelectorLoader | None = None

    # ------------------------------------------------------------------
    # BlogEditor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        """
        Navigate to write page and wait for editor to be ready.

        Three overlays are polled unconditionally — all treated as
        unpredictably timed. Each is silently skipped when absent.

        If a publish popover is currently open it will block .se-content
        from becoming visible. We force-reload the page before checking,
        which dismisses any open overlay without side effects.
        """
        self._page.goto(self._write_url)
        self._page.wait_for_load_state("domcontentloaded")

        # If already on the write URL (e.g. popover was open from a previous
        # call), goto() may not actually reload the page. Force a reload to
        # dismiss any overlay so .se-content becomes visible again.
        if self._write_url.split("?")[0] in self._page.url:
            self._page.reload(wait_until="domcontentloaded")

        if "nid.naver.com" in self._page.url or "login" in self._page.url.lower():
            raise RuntimeError(
                "Redirected to login page. Session may have expired. "
                f"Current URL: {self._page.url}"
            )

        # Wait for .se-content directly inside #mainFrame with the full timeout.
        # Do NOT go through _frame() here — its internal 1-second probe fires
        # before the iframe finishes loading and falls back to the page object,
        # causing the subsequent wait_for to look outside the iframe.
        self._page.frame_locator(_MAIN_FRAME).locator(_EDITOR_BODY).wait_for(
            state="visible", timeout=30_000
        )

        self._wait_for_editor_ready(self._frame(), self._sel())

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

    def insert_text(self, text: str, newlines: int = 2) -> None:
        """
        Click the last paragraph container and type text.

        Uses editor_paragraph_container (p.se-text-paragraph).
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

    _HEADING_SIZE_MAP = {
        1: "size_38",
        2: "size_34",
        3: "size_30",
        4: "size_28",
        5: "size_24",
        6: "size_19",
    }

    def insert_heading(self, text: str, level: int = 2) -> None:
        """
        Insert a heading with Naver SE One's native subtitle formatting.

        Font sizes by level:
            H1: 38, H2: 34, H3: 30, H4: 28, H5: 24, H6: 19

        Sequence (from interactive debug):
            0. Click last paragraph to position cursor in body area
            1. Click heading_trigger ("본문" dropdown)
            2. Click heading_button ("소제목")
            3. Type the heading text
            4. Select text (Home → Shift+End) → size_trigger → level size
            5. Click bold_button ("굵게")
            6. Click paragraph to deselect → Enter (exits subtitle)

        Falls back to insert_text for unsupported scenarios.
        """
        frame = self._frame()
        sel   = self._sel()

        # Step 0: Position cursor in body area (toolbar is inactive without this)
        last_para = sel.locator(frame, "editor_paragraph_container").last
        last_para.wait_for(state="visible", timeout=5_000)
        last_para.click()

        # Step 1: Open paragraph style dropdown
        trigger = sel.locator(frame, "heading_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self.insert_text(text, 1)
            return

        # Step 2: Click "소제목"
        heading_btn = sel.locator(frame, "heading_button")
        if not click_if_visible(heading_btn, timeout_ms=3_000):
            self.insert_text(text, 1)
            return

        # Step 3: Type heading text
        self._page.keyboard.type(text)

        # Step 4: Select text → change font size by level
        self._page.keyboard.press("Home")
        self._page.keyboard.press("Shift+End")
        size_key = self._HEADING_SIZE_MAP.get(level, "size_34")
        size_trigger = sel.locator(frame, "size_trigger")
        if click_if_visible(size_trigger, timeout_ms=3_000):
            size_btn = sel.locator(frame, size_key)
            click_if_visible(size_btn, timeout_ms=3_000)

        # Step 5: Bold
        bold_btn = sel.locator(frame, "bold_button")
        click_if_visible(bold_btn, timeout_ms=3_000)

        # Step 6: Click paragraph to deselect text, then Enter to exit subtitle
        last_para = sel.locator(frame, "editor_paragraph_container").last
        last_para.click()
        self._page.keyboard.press("Enter")

    def insert_quote(self, text: str) -> None:
        """
        Insert a quote block with Naver SE One's native quote formatting.

        Sequence (from interactive debug):
            0. Click last paragraph to position cursor in body area
            1. Click quote_trigger ("인용구 선택" dropdown)
            2. Click quote_1 ("인용구 1" style) — cursor lands inside quote
            3. Type text (cursor is already in quote content)
            4. Click bottom of .se-content to exit quote → creates new paragraph

        Falls back to insert_text for unsupported scenarios.
        """
        frame = self._frame()
        sel   = self._sel()

        # Step 0: Position cursor in body area
        last_para = sel.locator(frame, "editor_paragraph_container").last
        last_para.wait_for(state="visible", timeout=5_000)
        last_para.click()

        # Step 1: Open quote dropdown
        trigger = sel.locator(frame, "quote_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            self.insert_text(text, 2)
            return

        # Step 2: Select "인용구 1" — cursor lands inside quote automatically
        quote_btn = sel.locator(frame, "quote_1")
        if not click_if_visible(quote_btn, timeout_ms=3_000):
            self.insert_text(text, 2)
            return

        # Step 3: Type directly (cursor is already in quote content)
        self._page.keyboard.type(text)

        # Step 4: Click bottom of editor body to exit quote block
        self._click_editor_bottom(frame)

    def insert_divider(self) -> None:
        """
        Insert a horizontal divider with Naver SE One's native formatting.

        Sequence:
            0. Click last paragraph to position cursor in body area
            1. Click divider_trigger ("구분선 선택" dropdown)
            2. Click divider_2 ("구분선 2" style)
            3. Click bottom of editor body to exit divider
        """
        frame = self._frame()
        sel   = self._sel()

        # Step 0: Position cursor in body area
        last_para = sel.locator(frame, "editor_paragraph_container").last
        last_para.wait_for(state="visible", timeout=5_000)
        last_para.click()

        # Step 1: Open divider dropdown
        trigger = sel.locator(frame, "divider_trigger")
        if not click_if_visible(trigger, timeout_ms=3_000):
            return

        # Step 2: Select "구분선 2"
        divider_btn = sel.locator(frame, "divider_2")
        if not click_if_visible(divider_btn, timeout_ms=3_000):
            return

        # Step 3: Click bottom of editor to exit
        self._click_editor_bottom(frame)

    def upload_file(self, path: str) -> None:
        """
        Upload a file via toolbar button.

        Raises FileNotFoundError if path does not exist.
        """
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

        # Library sidebar appears after upload — poll as it may be slow.
        dismiss_polling(
            locator    = sel.locator(frame, "library_close").first,
            timeout_ms = 5_000,
        )

        sel.locator(frame, "editor_image").last.wait_for(
            state="visible", timeout=10_000
        )

    def set_representative_media(self, index: int) -> None:
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
                f"set_representative_media(index={index}) failed: "
                f"JS returned {result!r}"
            )

        wait_until_attached(
            sel.locator(frame, "editor_image_rep_selected").first,
            timeout_ms=5_000,
        )

    def move_cursor(self, position: CursorPosition = "end") -> None:
        """
        Reposition the cursor.

        'end'   -> click last paragraph, press Ctrl+End
        'start' -> click first paragraph, press Ctrl+Home
        """
        frame = self._frame()
        sel   = self._sel()
        container = sel.locator(frame, "editor_paragraph_container")

        if position == "start":
            container.first.click()
            self._page.keyboard.press("Control+Home")
        else:
            container.last.click()
            self._page.keyboard.press("Control+End")

    def publish(self, schedule_at: datetime | None = None) -> None:
        """
        Open the publish popover, configure options, and confirm.

        dry_run=True behaviour
        ----------------------
        The popover is opened and schedule options are set normally so the
        result can be inspected visually. Only the final "발행하기" confirm
        button is skipped — the post is never actually published.

        Args:
            schedule_at: KST-aware datetime for reserved publish, or None for
                         immediate publish. When set, clicks the "예약" radio
                         and sets hour/minute before confirming.
        """
        # Step 1: open popover — always, even in dry_run
        self._click_publish_trigger()

        # Step 2: configure reservation UI if needed — always, even in dry_run
        if schedule_at is not None:
            self._wait_for_popover_ready()
            self._set_scheduled_publish(schedule_at)

        # Step 3: confirm — skipped in dry_run
        if self._dry_run:
            label = schedule_at.isoformat() if schedule_at else "immediate"
            print(
                f"[SmartEditorOne] DRY RUN — confirm skipped (schedule_at={label}). "
                f"팝오버를 수동으로 닫거나 그냥 두면 됩니다.",
                file=sys.stderr,
            )
            return

        self._click_publish_confirm()
        self._wait_for_publish_complete()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _wait_for_publish_complete(self, timeout: int = 15_000) -> None:
        """Wait for Naver to finish publishing and navigate away from the editor."""
        try:
            self._page.wait_for_url(
                lambda url: "Redirect=Write" not in url,
                timeout=timeout,
            )
        except Exception:
            pass
        time.sleep(1)

    @staticmethod
    def _round_minute_to_10(minute: int) -> str:
        """
        Floor ``minute`` to the nearest multiple of 10 and return as
        a zero-padded 2-character string.

        Naver's reservation UI exposes minute values only in steps of 10
        (00, 10, 20, 30, 40, 50).  We always floor (never ceil) so that
        the scheduled time never overshoots the caller's intent.

        Examples:
            0  → "00"
            9  → "00"
            15 → "10"
            37 → "30"
            55 → "50"
            59 → "50"
        """
        return f"{(minute // 10) * 10:02d}"

    def _set_scheduled_publish(self, schedule_at: datetime) -> None:
        """
        Interact with Naver's reservation UI inside the publish popover.

        Why JS evaluate instead of Playwright click
        -------------------------------------------
        The reservation radio input is covered by a <label> element that
        intercepts pointer events. All Playwright .click() variants fail
        with "label intercepts pointer events". The only reliable approach
        is document.querySelector(...).click() via frame.evaluate(), which
        bypasses the pointer-event interception entirely.

        frame.evaluate() requires a real Frame object (page.frames[N]),
        NOT a FrameLocator — find_js_frame() with url_fragment resolves it.

        Sequence
        --------
        1. JS click "예약" radio   → input[name=radio_time][value=pre]
        2. Select hour             → select[class*=hour_option]
        3. Select minute           → select[class*=minute_option] (floored to 10)

        Args:
            schedule_at: KST-aware datetime whose hour/minute are used.
        """
        hour_str   = f"{schedule_at.hour:02d}"  # "00"–"23" (Naver select values are zero-padded)
        minute_str = self._round_minute_to_10(schedule_at.minute)

        # Real Frame object needed for evaluate() — FrameLocator doesn't support it.
        # PostWriteForm is the iframe that contains the publish popover.
        js_frame = find_js_frame(self._page, url_fragment="PostWriteForm")

        # Step 1: click the "예약" radio via JS (label intercepts pointer events)
        js_frame.evaluate(
            """() => {
                const el = document.querySelector(
                    'input[name="radio_time"][value="pre"]'
                );
                if (el) el.click();
            }"""
        )

        # Steps 2-3: select hour/minute via Playwright (selects work normally)
        sel   = self._sel()
        frame = self._popover_frame()
        select_option_by_value(sel.locator(frame, "publish_scheduled_hour"), hour_str)
        select_option_by_value(sel.locator(frame, "publish_scheduled_min"),  minute_str)

    def _sel(self) -> SelectorLoader:
        """Return cached SelectorLoader — loaded once, reused for the lifetime of the editor."""
        if self._sel_cache is None:
            if self._sel_source is not None:
                self._sel_cache = self._sel_source.load("editor")
            else:
                self._sel_cache = SelectorLoader.load(_EDITOR_JSON)
        return self._sel_cache

    def _click_editor_bottom(self, frame) -> None:
        """
        Click the bottom of .se-content to create a new empty paragraph.

        Used to exit quote/list blocks that trap the cursor.
        Clicking below the last block in the editor body creates a new
        normal paragraph and moves the cursor there.
        """
        editor_body = frame.locator(_EDITOR_BODY)
        box = editor_body.bounding_box()
        if box:
            editor_body.click(position={
                "x": box["width"] / 2,
                "y": box["height"] - 5,
            })

    def _frame(self):
        """Editor content frame — checks .se-content visibility (for editor actions)."""
        return find_editor_frame(self._page, _MAIN_FRAME, _EDITOR_BODY)

    def _popover_frame(self):
        """
        Publish popover frame — always returns #mainFrame directly.

        find_editor_frame() checks .se-content visibility, which fails when
        the publish popover overlays the editor. This method bypasses that
        check and returns the raw FrameLocator so popover elements can always
        be found inside mainFrame.
        """
        return self._page.frame_locator(_MAIN_FRAME).first

    def _wait_for_popover_ready(self, timeout_ms: int = 5_000) -> None:
        """
        Wait until the publish popover's reservation radio is attached to DOM.

        Triggered after _click_publish_trigger() — the popover renders
        asynchronously and the reservation elements may not exist yet when
        _set_scheduled_publish() runs immediately after the trigger click.
        """
        frame = self._popover_frame()
        sel   = self._sel()
        try:
            sel.locator(frame, "publish_scheduled").wait_for(
                state="attached", timeout=timeout_ms
            )
        except Exception:
            # Fallback: simple sleep so at least partial rendering occurs
            time.sleep(1.0)

    def _click_publish_trigger(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        # The publish button lives inside #mainFrame.
        # Use _popover_frame() (direct frame_locator) to avoid the
        # 1-second .se-content visibility probe in _frame().
        for ctx in (self._popover_frame(), self._page):
            if click_if_visible(sel.locator(ctx, "toolbar_publish"), timeout):
                return

    def _click_publish_confirm(self, timeout: int = 5_000) -> None:
        sel = self._sel()
        for ctx in (self._page, self._popover_frame()):
            if click_if_visible(sel.locator(ctx, "publish_confirm"), timeout):
                return
