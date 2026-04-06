"""
cli/session_manager.py
-----------------------
세션 생명주기 관리.

책임:
    validate        -세션 유효성 확인 (headless 네이버 접속)
    assisted_login  -브라우저 열고 ID/PW를 Playwright 키보드로 자동 입력
    ensure          -validate → assisted_login 순차 시도
    recover         -작업 중 세션 만료 시 복구

사용:
    mgr = SessionManager(session_store, playwright, browser_config)
    state = mgr.ensure(account)          # 유효한 세션 반환 (없으면 로그인)
    state = mgr.recover(account)         # 작업 중 만료 시 재시도

로그인 입력 방식
----------------
Playwright CDP 기반 keyboard.type()은 실제 keydown/keypress/input/keyup
이벤트 시퀀스를 발생시킨다. 합성 이벤트와 달리 타이핑 이력이 남아
네이버 봇 감지 휴리스틱을 우회하기 쉽다.

각 문자 사이 delay에 랜덤 지터(80~180ms)를 주어 인간 타이핑과 유사하게 만든다.
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

    def ensure(self, account: dict[str, Any]) -> dict:
        """유효한 세션을 반환한다. 없으면 로그인 과정을 거친다.

        순서: 기존 세션 로드 → 유효성 확인 → assisted_login
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

        # 2. 수동 로그인 (브라우저 + 확장 프로그램 ID/PW 복사 툴바)
        state = self.assisted_login(account, cfg)
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
        try:
            browser = self._pw.chromium.launch(headless=True)
            ctx = build_context(browser, browser_config, storage_state=state)
            page = ctx.new_page()
            page.goto(check_url, wait_until="domcontentloaded", timeout=15_000)

            logged_in = "nidlogin" not in page.url

            page.close()
            ctx.close()
            browser.close()
            return logged_in
        except Exception as exc:
            log.debug("validate 실패: %s", exc)
            return False

    @staticmethod
    def _has_display() -> bool:
        """GUI 브라우저를 띄울 수 있는 환경인지 확인."""
        if sys.platform == "win32" or sys.platform == "darwin":
            return True
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def assisted_login(self, account: dict[str, Any], browser_config: dict[str, Any] | None = None) -> dict | None:
        """브라우저를 열고 Playwright 키보드로 ID/PW를 자동 입력하여 로그인한다.

        각 글자마다 실제 keydown/keypress/input/keyup 이벤트가 발생하고,
        입력 간 80~180ms 랜덤 지터가 들어가 인간 타이핑과 유사하다.

        CAPTCHA 등 추가 인증이 필요하면 사용자가 직접 해결하도록
        브라우저를 열어둔 상태로 최대 5분 대기한다.
        """
        username = account["username"]
        password = account["password"]

        if not self._has_display():
            log.error(
                "[%s] 디스플레이 없음 — assisted_login 불가.\n"
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
            return None

        blog_id = account.get("blog_id", username)
        write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"

        browser = None
        ctx = None
        try:
            browser = self._pw.chromium.launch(headless=False)
            ctx = build_context(browser, browser_config)
            page = ctx.new_page()

            # 1. 로그인 페이지 로딩
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # 2. ID 필드 찾아서 클릭 후 자동 타이핑
            id_field = _LOGIN_SEL.locator(page, "naver_login_id")
            id_field.wait_for(state="visible", timeout=10_000)
            id_field.click()
            _type_humanlike(id_field, username)

            # 3. PW 필드로 이동 — Tab 키로 자연스럽게 포커스 이동
            page.keyboard.press("Tab")
            page.wait_for_timeout(random.randint(150, 350))

            pw_field = _LOGIN_SEL.locator(page, "naver_login_pw")
            pw_field.wait_for(state="visible", timeout=5_000)
            _type_humanlike(pw_field, password)

            # 4. 입력 완료 후 짧은 지연 (사람이 버튼 찾는 시간)
            page.wait_for_timeout(random.randint(300, 700))

            # 5. 로그인 버튼 클릭
            submit_btn = _LOGIN_SEL.locator(page, "naver_login_submit")
            submit_btn.click()

            log.info("[%s] ID/PW 자동 입력 완료 — 리다이렉트 대기 중", username)
            print(f"          >> 로그인 중... CAPTCHA 등 추가 인증이 필요하면 직접 처리해주세요. ({username})")

            # 6. 로그인 완료 대기 (CAPTCHA 등 처리 시간 포함, 최대 5분)
            page.wait_for_url(
                lambda url: "nidlogin" not in url and "naver.com" in url,
                timeout=self._max_manual_wait_ms,
            )

            # 7. 블로그 글쓰기 URL로 이동하여 세션 확인
            page.goto(write_url, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(3_000)

            if "nidlogin" in page.url:
                log.warning("[%s] 로그인 후 블로그 접속 시 세션 무효 (url=%s)", username, page.url)
                return None

            state = ctx.storage_state()
            return state
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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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
