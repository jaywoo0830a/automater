#!/usr/bin/env bash
# run/dev.sh
# ----------
# 개발 환경을 띄운다: 가상환경 활성화 + 유용한 개발 도구 실행.
#
# Usage:
#   bash ./run/dev.sh              # 가상환경 활성화 후 셸 진입
#   bash ./run/dev.sh --watch      # 파일 변경 감지 시 unit 테스트 자동 재실행
#   bash ./run/dev.sh --capture    # 셀렉터 캡처 도구 실행 (Chromium 오픈)
#   bash ./run/dev.sh --session    # 네이버 로그인 후 session_state.json 저장

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

_print_help() {
    echo "Usage:"
    echo "  bash ./run/dev.sh              # 가상환경 활성화 후 셸 진입"
    echo "  bash ./run/dev.sh --watch      # 파일 변경 시 unit 테스트 자동 재실행"
    echo "  bash ./run/dev.sh --capture    # 셀렉터 캡처 도구 실행"
    echo "  bash ./run/dev.sh --session    # 네이버 로그인 후 session_state.json 저장"
}

MODE="${1:---shell}"

# ── --help: venv 체크 전에 처리 ──────────────────────────────────────────────
if [ "${MODE}" = "--help" ] || [ "${MODE}" = "-h" ]; then
    _print_help
    exit 0
fi

# ── 가상환경 확인 ────────────────────────────────────────────────────────────
cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: .venv not found. Run: bash ./run/init.sh"
    exit 1
fi

source "${VENV_DIR}/bin/activate"

echo "========================================"
echo "  automator — dev environment"
echo "========================================"
echo "Project root : ${PROJECT_ROOT}"
echo "Python       : $(python --version)"
echo "Activated    : ${VIRTUAL_ENV}"
echo ""

case "${MODE}" in

  # ── 기본: 활성화된 셸로 진입 ─────────────────────────────────────────────────
  --shell)
    echo "개발 환경이 활성화됐습니다."
    echo ""
    echo "자주 쓰는 명령:"
    echo "  bash ./run/test.sh                   # unit tests"
    echo "  bash ./run/test.sh --pipeline <1-8>  # 파이프라인 단일 시나리오"
    echo "  bash ./run/dev.sh --watch            # 파일 변경 감지 자동 테스트"
    echo "  bash ./run/dev.sh --capture          # 셀렉터 캡처 도구"
    echo "  bash ./run/dev.sh --session          # 네이버 세션 저장"
    echo ""
    exec "${SHELL}"
    ;;

  # ── Watch: unit 테스트 자동 재실행 ───────────────────────────────────────────
  --watch)
    echo "Mode : watch (unit 테스트 자동 재실행)"
    echo "       automator/ 또는 tests/ 파일 변경 시 자동 실행됩니다."
    echo "       종료: Ctrl+C"
    echo ""

    UNIT_TESTS=(
        tests/test_job_unit.py
        tests/test_editor_unit.py
        tests/test_selector_unit.py
        tests/test_config.py
        tests/test_title_unit.py
        tests/test_layout_unit.py
        tests/test_paragraph_generator.py
    )

    if python -c "import pytest_watch" 2>/dev/null; then
        pytest-watch "${UNIT_TESTS[@]}" -- -m unit -v
    elif command -v entr &>/dev/null; then
        echo "(entr 사용 — pip install pytest-watch 으로 더 정교한 감지 가능)"
        echo ""
        find automator tests -name "*.py" | entr -c \
            pytest "${UNIT_TESTS[@]}" -m unit -v
    else
        echo "ERROR: pytest-watch 또는 entr이 필요합니다."
        echo ""
        echo "설치 방법:"
        echo "  pip install pytest-watch   # 권장"
        echo "  brew install entr          # macOS 대안"
        exit 1
    fi
    ;;

  # ── Capture: 셀렉터 캡처 도구 ────────────────────────────────────────────────
  --capture)
    echo "Mode : selector capture (Chromium 오픈)"
    echo "       selectors/naver/editor.json 업데이트 후 종료됩니다."
    echo ""

    if [ ! -f scripts/capture_selectors.py ]; then
        echo "ERROR: scripts/capture_selectors.py not found"
        exit 1
    fi

    python scripts/capture_selectors.py
    ;;

  # ── Session: 네이버 로그인 후 세션 저장 ──────────────────────────────────────
  --session)
    echo "Mode : session capture"
    echo "       브라우저가 열리면 직접 로그인하세요."
    echo "       로그인 완료 후 Enter를 누르면 session_state.json이 저장됩니다."
    echo ""

    if [ ! -f .env ]; then
        echo "ERROR: .env not found. cp .env.example .env 후 NAVER_BLOG_ID를 설정하세요."
        exit 1
    fi

    python - << 'PYEOF'
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
session_path = os.getenv("SESSION_PATH", "session_state.json")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx     = browser.new_context()
    page    = ctx.new_page()
    page.goto("https://nid.naver.com/nidlogin.login")
    print("  브라우저에서 네이버 로그인을 완료하세요.")
    input("  로그인 완료 후 Enter 키를 누르세요... ")
    ctx.storage_state(path=session_path)
    browser.close()

print(f"  ✓ 세션 저장 완료: {session_path}")
PYEOF
    ;;

  # ── Help / unknown ────────────────────────────────────────────────────────────
  *)
    echo "Unknown option: ${MODE}"
    echo ""
    _print_help
    exit 1
    ;;

esac
