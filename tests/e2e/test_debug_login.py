"""
tests/e2e/test_debug_login.py
------------------------------
로그인 디버그 테스트.

확장 프로그램으로 ID/PW 복사 툴바를 표시한 뒤,
사용자가 직접 로그인하여 결과를 확인한다.

Run:
    pytest tests/e2e/test_debug_login.py -v -s
"""

import os
import shutil
import tempfile

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from cli.session_manager import _build_login_ext

load_dotenv()

NAVER_ID = os.getenv("NAVER_ID", "")
NAVER_PW = os.getenv("NAVER_PW", "")
NAVER_BLOG_ID = os.getenv("NAVER_BLOG_ID", "")
LOGIN_URL = "https://nid.naver.com/nidlogin.login"


def _print_step(step: str, page) -> None:
    print(f"\n{'─'*60}")
    print(f"  [{step}]")
    print(f"  URL   : {page.url}")
    print(f"  Title : {page.title()}")
    print(f"{'─'*60}")


@pytest.mark.e2e
def test_debug_login():
    """확장 프로그램 ID/PW 툴바 + 사용자 직접 로그인."""
    if not NAVER_ID or not NAVER_PW:
        pytest.skip("NAVER_ID / NAVER_PW 없음")

    blog_id = NAVER_BLOG_ID or NAVER_ID
    write_url = f"https://blog.naver.com/{blog_id}?Redirect=Write&"
    ext_dir = _build_login_ext(NAVER_ID, NAVER_PW)
    user_data_dir = tempfile.mkdtemp(prefix="login_debug_")

    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                slow_mo=300,
                args=[
                    f"--disable-extensions-except={ext_dir}",
                    f"--load-extension={ext_dir}",
                ],
            )
            page = ctx.new_page()

            # 1. 로그인 페이지 (확장 프로그램이 툴바 삽입)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            _print_step("1. 브라우저 열림 — 직접 로그인해주세요", page)

            # 2. 사용자가 로그인할 때까지 대기 (최대 5분)
            page.wait_for_url(
                lambda url: "nidlogin" not in url and "naver.com" in url,
                timeout=300_000,
            )
            _print_step("2. 로그인 완료", page)

            # 3. 블로그 글쓰기 URL로 이동
            page.goto(write_url, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(3_000)
            _print_step("3. 블로그 글쓰기 URL 이동 후", page)

            if "nidlogin" in page.url:
                print(f"  ✗ 실패 — 로그인 페이지로 리다이렉트됨")
            else:
                print(f"  ✓ 성공 — 글쓰기 페이지 접근 확인")

            page.close()
            ctx.close()
    finally:
        shutil.rmtree(ext_dir, ignore_errors=True)
        shutil.rmtree(user_data_dir, ignore_errors=True)
