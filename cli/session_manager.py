"""
cli/session_manager.py
-----------------------
세션 생명주기 관리.

책임:
    validate   — 세션 유효성 확인 (headless 네이버 접속)
    auto_login — 자동 로그인 시도 (캡챠 없을 때)
    manual_login — headless=false 브라우저 열어 사람 개입
    ensure     — validate → auto_login → manual_login 순차 시도
    recover    — 작업 중 세션 만료 시 복구

사용:
    mgr = SessionManager(session_store, playwright, browser_config)
    state = mgr.ensure(account)          # 유효한 세션 반환 (없으면 로그인)
    state = mgr.recover(account)         # 작업 중 만료 시 재시도
"""

from __future__ import annotations

import logging
from typing import Any

from automator.browser import build_context, merge_browser_config

log = logging.getLogger(__name__)

LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_HOME = "https://www.naver.com"

# 로그인 상태 확인용 셀렉터
_LOGGED_IN_SELECTORS = ".MyView, .sc_login, #minime"

# 세션 만료 판단용 URL 패턴
SESSION_EXPIRED_PATTERNS = ("nidlogin", "sso/cross-domain", "login")


def is_session_error(url: str = "", error_msg: str = "") -> bool:
    """URL이나 에러 메시지로 세션 만료를 판단한다."""
    text = (url + " " + error_msg).lower()
    return any(p in text for p in SESSION_EXPIRED_PATTERNS)


class SessionManager:
    """세션 생명주기 관리자."""

    def __init__(
        self,
        session_store,
        playwright,
        global_browser_config: dict[str, Any] | None = None,
    ) -> None:
        self._store = session_store
        self._pw = playwright
        self._global_browser_cfg = global_browser_config or {}
        self._max_manual_wait_ms = 300_000  # 5분

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure(self, account: dict[str, Any]) -> dict:
        """유효한 세션을 반환한다. 없으면 로그인 과정을 거친다.

        순서: 기존 세션 로드 → 유효성 확인 → 자동 로그인 → 수동 로그인
        """
        username = account["username"]
        cfg = self._resolve_config(account)

        # 1. 기존 세션 로드
        state = self._load(account)
        if state and self.validate(state, cfg):
            log.info("[%s] 세션 유효 — 재사용", username)
            return state

        if state:
            log.info("[%s] 세션 만료 — 갱신 필요", username)
        else:
            log.info("[%s] 세션 없음 — 로그인 필요", username)

        # 2. 자동 로그인 시도
        state = self.auto_login(account, cfg)
        if state and self.validate(state, cfg):
            self._save(account, state)
            log.info("[%s] 자동 로그인 성공", username)
            return state

        # 3. 수동 로그인 (캡챠 등)
        log.info("[%s] 자동 로그인 실패 — 수동 로그인 필요", username)
        state = self.manual_login(account, cfg)
        self._save(account, state)
        log.info("[%s] 수동 로그인 완료", username)
        return state

    def recover(self, account: dict[str, Any]) -> dict:
        """작업 중 세션 만료 시 복구. ensure와 동일하지만 로그 메시지가 다르다."""
        username = account["username"]
        log.warning("[%s] 세션 만료 감지 — 복구 시도", username)
        return self.ensure(account)

    def validate(self, state: dict, browser_config: dict[str, Any] | None = None) -> bool:
        """세션이 아직 유효한지 headless로 확인."""
        try:
            browser = self._pw.chromium.launch(headless=True)
            ctx = build_context(browser, browser_config, storage_state=state)
            page = ctx.new_page()
            page.goto(NAVER_HOME, wait_until="domcontentloaded", timeout=15_000)

            logged_in = False
            try:
                logged_in = page.locator(_LOGGED_IN_SELECTORS).first.is_visible(timeout=5_000)
            except Exception:
                pass

            page.close()
            ctx.close()
            browser.close()
            return logged_in
        except Exception as exc:
            log.debug("validate 실패: %s", exc)
            return False

    def auto_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict | None:
        """headless 자동 로그인 시도. 캡챠 시 None 반환."""
        try:
            browser = self._pw.chromium.launch(headless=True)
            ctx = build_context(browser, browser_config)
            page = ctx.new_page()
            page.goto(LOGIN_URL)

            from automator.selector_loader import SelectorLoader
            login_sel = SelectorLoader.load("selectors/naver/login.yaml")

            login_sel.locator(page, "naver_login_id").fill(account["username"])
            login_sel.locator(page, "naver_login_pw").fill(account["password"])
            login_sel.locator(page, "naver_login_submit").click()

            page.wait_for_url(
                lambda url: "nidlogin" not in url,
                timeout=15_000,
            )

            if any(p in page.url.lower() for p in ("captcha", "deviceConfirm", "protect")):
                page.close()
                ctx.close()
                browser.close()
                return None

            state = ctx.storage_state()
            page.close()
            ctx.close()
            browser.close()
            return state
        except Exception as exc:
            log.debug("auto_login 실패: %s", exc)
            try:
                browser.close()
            except Exception:
                pass
            return None

    def manual_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict:
        """headless=false 브라우저를 열어 사람이 로그인할 때까지 대기."""
        print(f"          → 브라우저를 엽니다. 로그인을 완료해주세요. ({account['username']})")

        browser = self._pw.chromium.launch(headless=False)
        ctx = build_context(browser, browser_config)
        page = ctx.new_page()
        page.goto(LOGIN_URL)

        try:
            page.wait_for_url(
                lambda url: "nidlogin" not in url and "naver.com" in url,
                timeout=self._max_manual_wait_ms,
            )
        except Exception:
            page.close()
            ctx.close()
            browser.close()
            raise TimeoutError(
                f"로그인 시간 초과 ({self._max_manual_wait_ms // 1000}초): {account['username']}"
            )

        state = ctx.storage_state()
        page.close()
        ctx.close()
        browser.close()
        return state

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_config(self, account: dict[str, Any]) -> dict[str, Any]:
        """글로벌 browser config + 계정별 오버라이드 머지."""
        return merge_browser_config(self._global_browser_cfg, account.get("browser"))

    def _load(self, account: dict[str, Any]) -> dict | None:
        username = account["username"]
        explicit_path = account.get("session", "")
        if explicit_path and hasattr(self._store, "load_path"):
            return self._store.load_path(explicit_path)
        return self._store.load(username)

    def _save(self, account: dict[str, Any], state: dict) -> None:
        username = account["username"]
        explicit_path = account.get("session", "")
        if explicit_path and hasattr(self._store, "save_path"):
            self._store.save_path(explicit_path, state)
        else:
            self._store.save(username, state)
