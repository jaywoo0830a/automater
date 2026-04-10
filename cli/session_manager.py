"""
cli/session_manager.py
-----------------------
세션 생명주기 관리.

책임:
    validate        -세션 유효성 확인 (headless 네이버 접속)
    auto_login      -브라우저 열고 Playwright 키보드로 ID/PW 자동 입력
    manual_login    -브라우저만 열고 사용자가 직접 ID/PW 입력
    ensure          -validate → auto/manual login 순차 시도
    recover         -작업 중 세션 만료 시 복구

사용:
    mgr = SessionManager(session_store, playwright, browser_config)
    state = mgr.ensure(account)                      # 자동 로그인 (기본)
    state = mgr.ensure(account, mode="manual")       # 수동 로그인
    state = mgr.recover(account)                     # 작업 중 만료 시 재시도

로그인 모드
-----------
auto (기본)
    Playwright CDP 기반 keyboard.type()으로 ID/PW를 자동 입력.
    실제 keydown/keypress/input/keyup 이벤트 시퀀스가 발생하며,
    각 문자 사이 80~180ms 랜덤 지터로 인간 타이핑과 유사하게 만든다.
    CAPTCHA/2차 인증이 뜨면 사용자가 직접 해결한다 (최대 5분 대기).

manual
    브라우저만 열고 ID/PW 입력은 사용자에게 완전히 맡긴다.
    자동 로그인이 봇 감지에 걸릴 때 대안으로 사용.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from typing import Any

from automator.browser import build_context, merge_browser_config
from automator.selector_loader import SelectorLoader

log = logging.getLogger(__name__)

LOGIN_URL = "https://nid.naver.com/nidlogin.login"

# 세션 만료 판단용 URL 패턴
SESSION_EXPIRED_PATTERNS = ("nidlogin", "sso/cross-domain", "login")

# 키 입력 간 지터 범위 (ms)
_TYPE_DELAY_MIN = 80
_TYPE_DELAY_MAX = 180

_LOGIN_SEL = SelectorLoader.load("selectors/naver/login.yaml")


def is_session_error(url: str = "", error_msg: str = "") -> bool:
    """URL이나 에러 메시지로 세션 만료를 판단한다."""
    text = (url + " " + error_msg).lower()
    return any(p in text for p in SESSION_EXPIRED_PATTERNS)


def _type_humanlike(locator, text: str) -> None:
    """Playwright Locator에 인간처럼 한 글자씩 타이핑한다.

    평균 delay는 랜덤(80~180ms)이며, press_sequentially가 내부적으로
    각 글자마다 keydown/keypress/input/keyup 이벤트를 생성한다.
    """
    # 평균값을 delay로 전달 (playwright는 단일 delay만 받음)
    avg_delay = random.randint(_TYPE_DELAY_MIN, _TYPE_DELAY_MAX)
    locator.press_sequentially(text, delay=avg_delay)


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

    def ensure(self, account: dict[str, Any], *, mode: str = "auto") -> dict:
        """유효한 세션을 반환한다. 없으면 로그인 과정을 거친다.

        Args:
            account: 계정 정보 (username, password, blog_id, session?, proxy?).
            mode:    "auto" — Playwright 키보드로 자동 입력
                     "manual" — 브라우저만 열고 사용자가 직접 입력

        순서: 기존 세션 로드 → 유효성 확인 → (auto|manual) login
        """
        username = account["username"]
        cfg = self._resolve_config(account)

        # 1. 기존 세션 로드
        blog_id = account.get("blog_id", username)
        state = self._load(account)
        if state and self.validate(state, blog_id, cfg):
            log.info("[%s] 세션 유효 -재사용", username)
            return state

        if state:
            log.info("[%s] 세션 만료 -갱신 필요", username)
        else:
            log.info("[%s] 세션 없음 -로그인 필요", username)

        # 2. 로그인 (모드에 따라 auto/manual 분기)
        if mode == "manual":
            state = self.manual_login(account, cfg)
        else:
            state = self.auto_login(account, cfg)

        if state and self.validate(state, blog_id, cfg):
            self._save(account, state)
            log.info("[%s] 로그인 성공", username)
            return state

        raise RuntimeError(f"[{username}] 로그인 실패 — 세션을 확보할 수 없습니다")

    def recover(self, account: dict[str, Any]) -> dict:
        """작업 중 세션 만료 시 복구. ensure와 동일하지만 로그 메시지가 다르다."""
        username = account["username"]
        log.warning("[%s] 세션 만료 감지 -복구 시도", username)
        return self.ensure(account)

    def validate(
        self,
        state: dict,
        blog_id: str,
        browser_config: dict[str, Any] | None = None,
    ) -> bool:
        """세션이 아직 유효한지 headless로 확인.

        실제 글쓰기 페이지(blog.naver.com/{blog_id}?Redirect=Write&)에 접속하여
        nidlogin으로 리다이렉트되면 만료로 판단한다.
        """
        check_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
        browser = None
        ctx = None
        try:
            browser = self._pw.chromium.launch(headless=True)
            ctx = build_context(browser, browser_config, storage_state=state)
            page = ctx.new_page()
            page.goto(check_url, wait_until="domcontentloaded", timeout=15_000)

            logged_in = "nidlogin" not in page.url
            return logged_in
        except Exception as exc:
            log.debug("validate 실패: %s", exc)
            return False
        finally:
            try:
                if ctx is not None:
                    ctx.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass

    @staticmethod
    def _has_display() -> bool:
        """GUI 브라우저를 띄울 수 있는 환경인지 확인."""
        if sys.platform == "win32" or sys.platform == "darwin":
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def auto_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict | None:
        """브라우저를 열고 Playwright 키보드로 ID/PW를 자동 입력하여 로그인한다.

        각 글자마다 실제 keydown/keypress/input/keyup 이벤트가 발생하고,
        입력 간 80~180ms 랜덤 지터가 들어가 인간 타이핑과 유사하다.

        CAPTCHA 등 추가 인증이 필요하면 사용자가 직접 해결하도록
        브라우저를 열어둔 상태로 최대 5분 대기한다.
        """
        username = account["username"]
        password = account["password"]

        if not self._check_display(username):
            return None

        def _do_login(page) -> None:
            # 1. ID 필드 클릭 + 자동 타이핑
            id_field = _LOGIN_SEL.locator(page, "naver_login_id")
            id_field.wait_for(state="visible", timeout=10_000)
            id_field.click()
            _type_humanlike(id_field, username)

            # 2. Tab으로 PW 필드 이동 (자연스러운 포커스 전환)
            page.keyboard.press("Tab")
            page.wait_for_timeout(random.randint(150, 350))

            pw_field = _LOGIN_SEL.locator(page, "naver_login_pw")
            pw_field.wait_for(state="visible", timeout=5_000)
            _type_humanlike(pw_field, password)

            # 3. 사람이 버튼 찾는 시간 시뮬레이션
            page.wait_for_timeout(random.randint(300, 700))

            # 4. 로그인 버튼 클릭
            submit_btn = _LOGIN_SEL.locator(page, "naver_login_submit")
            submit_btn.click()

            log.info("[%s] ID/PW 자동 입력 완료 — 리다이렉트 대기 중", username)
            log.info("[%s] 로그인 중... CAPTCHA/2차 인증이 뜨면 직접 처리해주세요.", username)

        return self._login_flow(account, browser_config, _do_login)

    def manual_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict | None:
        """브라우저만 열고 사용자가 직접 ID/PW를 입력하도록 한다.

        auto_login이 봇 감지에 걸릴 때 대안으로 사용.
        최대 5분 대기하며 사용자가 로그인을 완료할 때까지 기다린다.
        """
        username = account["username"]

        if not self._check_display(username):
            return None

        def _do_login(page) -> None:
            # ID/PW 터미널에 출력 (사용자가 복사하기 쉽도록)
            print()
            print(f"          >> 브라우저가 열렸습니다. 직접 로그인해주세요. ({username})")
            print(f"          >> ID: {account['username']}")
            print(f"          >> PW: {account['password']}")
            print()
            log.info("[%s] 수동 로그인 대기 중 (최대 5분)", username)

        return self._login_flow(account, browser_config, _do_login)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_display(self, username: str) -> bool:
        """디스플레이 사용 가능 여부 확인. 실패 시 에러 로그 출력."""
        if self._has_display():
            return True
        log.error(
            "[%s] 디스플레이 없음 — 로그인 불가.\n"
            "  해결 방법:\n"
            "    1) 로컬에서 세션 준비 후 서버로 복사:\n"
            "       python -m cli campaign.yaml --prepare\n"
            "       python -m cli --export-sessions ./sessions_backup/\n"
            "       scp -r ./sessions_backup/ server:~/automator/\n"
            "       python -m cli --import-sessions ./sessions_backup/\n"
            "    2) X11 포워딩: ssh -X user@server\n"
            "    3) DISPLAY 환경변수 설정 (VNC/xvfb 사용 시)",
            username,
        )
        return False

    def _login_flow(
        self,
        account: dict[str, Any],
        browser_config: dict[str, Any] | None,
        login_action,
    ) -> dict | None:
        """auto/manual 공통 로그인 플로우.

        브라우저 열기 → 로그인 페이지 → ``login_action(page)`` 실행 →
        리다이렉트 대기 → 블로그 글쓰기 페이지 검증 → storage_state 반환.
        """
        username = account["username"]
        blog_id = account.get("blog_id", username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

        browser = None
        ctx = None
        try:
            browser = self._pw.chromium.launch(headless=False)
            ctx = build_context(browser, browser_config)
            page = ctx.new_page()

            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # 로그인 액션 실행 (auto: 자동 타이핑, manual: 사용자 안내)
            login_action(page)

            # 리다이렉트 대기 (최대 5분 — CAPTCHA/2차인증/수동입력 시간 포함)
            page.wait_for_url(
                lambda url: "nidlogin" not in url and "naver.com" in url,
                timeout=self._max_manual_wait_ms,
            )

            # 블로그 글쓰기 URL로 이동하여 세션 확인
            page.goto(write_url, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(3_000)

            if "nidlogin" in page.url:
                log.warning("[%s] 로그인 후 블로그 접속 시 세션 무효 (url=%s)", username, page.url)
                return None

            return ctx.storage_state()
        except Exception as exc:
            log.warning("[%s] 로그인 실패: %s", username, exc)
            return None
        finally:
            try:
                if ctx is not None:
                    ctx.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass

    def _resolve_config(self, account: dict[str, Any]) -> dict[str, Any]:
        """글로벌 browser config + 계정별 오버라이드 머지 + 프록시."""
        account_cfg = account.get("browser") or {}
        proxy = account.get("proxy")
        if proxy:
            account_cfg = {**account_cfg, "proxy": proxy}
        return merge_browser_config(self._global_browser_cfg, account_cfg)

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
