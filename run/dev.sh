#!/usr/bin/env bash
# run/dev.sh — 개발 환경 도구
#
#   (없음)       가상환경 활성화 후 셸 진입
#   --watch      파일 변경 시 unit 테스트 자동 재실행
#   --session    네이버 로그인 후 세션 파일 저장
#   --capture    셀렉터 캡처 도구 실행 (Chromium 오픈)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

_require_venv() {
    if [ ! -d "${VENV_DIR}" ]; then
        echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
        exit 1
    fi
    source "${VENV_DIR}/bin/activate"
}

MODE="${1:---shell}"
cd "${PROJECT_ROOT}"

case "${MODE}" in

  --shell)
    _require_venv
    echo "  Python : $(python --version)"
    echo "  루트   : ${PROJECT_ROOT}"
    echo ""
    echo "  bash ./run/test.sh              # unit 테스트"
    echo "  bash ./run/test.sh --e2e        # e2e smoke"
    echo "  bash ./run/test.sh --all        # 전체"
    echo "  bash ./run/factory.sh status    # 공장 현황"
    echo ""
    exec "${SHELL}"
    ;;

  --watch)
    _require_venv
    echo "  automator/ tests/ factory/ 변경 시 unit 테스트 자동 실행 (Ctrl+C 종료)"
    echo ""

    UNIT_TESTS=(
        tests/test_job_unit.py
        tests/test_editor_unit.py
        tests/test_selector_unit.py
        tests/test_config.py
        tests/test_title_unit.py
        tests/test_layout_unit.py
        tests/test_paragraph_generator.py
        tests/test_seo_option.py
        tests/test_seo_job_integration.py
        factory/tests/test_combo_generator.py
        factory/tests/test_dispatcher.py
    )

    if python -c "import pytest_watch" 2>/dev/null; then
        pytest-watch "${UNIT_TESTS[@]}" -- -v
    elif command -v entr &>/dev/null; then
        find automator tests factory -name "*.py" | entr -c pytest "${UNIT_TESTS[@]}" -v
    else
        echo "❌ pytest-watch 또는 entr 필요"
        echo "   pip install pytest-watch"
        exit 1
    fi
    ;;

  --session)
    _require_venv
    if [ ! -f .env ]; then
        echo "❌ .env 없음 — cp .env.example .env"
        exit 1
    fi
    echo "  브라우저가 열리면 네이버에 로그인하세요."
    echo "  완료 후 터미널에서 Enter 를 누르면 세션이 저장됩니다."
    echo ""
    python - << 'PYEOF'
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
session_path = os.getenv("SESSION_PATH", "session_state.json")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx  = browser.new_context()
    page = ctx.new_page()
    page.goto("https://nid.naver.com/nidlogin.login")
    input("  로그인 완료 후 Enter... ")
    ctx.storage_state(path=session_path)
    browser.close()

print(f"  ✅ 세션 저장: {session_path}")
PYEOF
    ;;

  --capture)
    _require_venv
    if [ ! -f scripts/capture_selectors.py ]; then
        echo "❌ scripts/capture_selectors.py 없음"
        exit 1
    fi
    echo "  셀렉터 캡처 — 결과: selectors/naver/editor.json"
    python scripts/capture_selectors.py
    ;;

  --help|-h)
    echo ""
    echo "  bash ./run/dev.sh              # 셸 진입"
    echo "  bash ./run/dev.sh --watch      # 파일 변경 감지 자동 테스트"
    echo "  bash ./run/dev.sh --session    # 네이버 세션 저장"
    echo "  bash ./run/dev.sh --capture    # 셀렉터 캡처"
    echo ""
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}  (--help 로 도움말 확인)"
    exit 1
    ;;

esac
