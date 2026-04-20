#!/usr/bin/env bash
# run/test.sh — 테스트 실행
#
# 자동 마킹: conftest.py가 디렉토리 기반으로 마커를 붙입니다.
#   tests/unit/          → @pytest.mark.unit
#   tests/integration/   → @pytest.mark.integration
#   tests/browser/       → @pytest.mark.browser
#   tests/e2e/           → @pytest.mark.e2e
#
# 사용법:
#   bash ./run/test.sh             # unit + integration + browser
#   bash ./run/test.sh --all       # + e2e
#   bash ./run/test.sh --session   # 네이버 세션 준비 (자동 로그인)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

# ── .env 로드 ────────────────────────────────────────────────────────────────
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -o allexport
    source "${PROJECT_ROOT}/.env"
    set +o allexport
fi

# ── venv ─────────────────────────────────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    source "${VENV_DIR}/bin/activate"
fi

MODE="${1:---default}"

case "${MODE}" in

  --default)
    pytest tests/unit/ tests/integration/ tests/browser/ -v
    ;;

  --all)
    pytest tests/unit/ tests/integration/ tests/browser/ tests/e2e/ -v
    ;;

  --session)
    echo "  네이버 세션 준비 (자동 로그인)"
    echo "  CAPTCHA/2차 인증이 뜨면 직접 처리하세요."
    echo ""
    python3 -c "
import os, random
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from automator.selector_loader import SelectorLoader

load_dotenv()
naver_id  = os.getenv('NAVER_ID', '')
naver_pw  = os.getenv('NAVER_PW', '')
blog_id   = os.getenv('NAVER_BLOG_ID', naver_id)
out_path  = os.getenv('SESSION_PATH', 'session_state.json')

if not naver_id or not naver_pw:
    print('  .env에 NAVER_ID, NAVER_PW를 설정하세요.')
    exit(1)

sel = SelectorLoader.load('selectors/naver/login.yaml')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx  = browser.new_context(locale='ko-KR', timezone_id='Asia/Seoul')
    page = ctx.new_page()
    page.goto('https://nid.naver.com/nidlogin.login', wait_until='domcontentloaded')

    id_field = sel.locator(page, 'naver_login_id')
    id_field.wait_for(state='visible', timeout=10_000)
    id_field.click()
    id_field.press_sequentially(naver_id, delay=random.randint(80, 180))

    page.keyboard.press('Tab')
    page.wait_for_timeout(random.randint(150, 350))

    pw_field = sel.locator(page, 'naver_login_pw')
    pw_field.wait_for(state='visible', timeout=5_000)
    pw_field.press_sequentially(naver_pw, delay=random.randint(80, 180))

    page.wait_for_timeout(random.randint(300, 700))
    sel.locator(page, 'naver_login_submit').click()

    print('  로그인 중... CAPTCHA/2차 인증이 뜨면 직접 처리하세요.')
    page.wait_for_url(
        lambda url: 'nidlogin' not in url and 'naver.com' in url,
        timeout=300_000,
    )

    page.goto(
        f'https://blog.naver.com/{blog_id}?Redirect=Write&',
        wait_until='domcontentloaded',
        timeout=15_000,
    )
    if 'nidlogin' in page.url:
        print('  세션 검증 실패 — 로그인 상태가 아닙니다.')
        browser.close()
        exit(1)

    ctx.storage_state(path=out_path)
    browser.close()

print(f'  세션 저장 완료: {out_path}')
"
    ;;

  --help|-h)
    cat << 'HELP'

  bash ./run/test.sh             # unit + integration + browser
  bash ./run/test.sh --all       # + e2e
  bash ./run/test.sh --session   # 네이버 세션 준비 (자동 로그인)

HELP
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}  (--help 로 도움말 확인)"
    exit 1
    ;;

esac

echo ""
echo "완료"
