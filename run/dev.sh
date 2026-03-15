#!/usr/bin/env bash
# run/dev.sh
# ----------
# 개발 환경 진입 및 개발 도구 실행.
#
# 명령어:
#   (없음)           가상환경 활성화 후 셸 진입
#   --watch          파일 변경 감지 시 unit 테스트 자동 재실행
#   --session        네이버 로그인 후 session_state.json 저장
#   --capture        셀렉터 캡처 도구 실행 (Chromium 오픈)
#   --factory-shell  factory 관련 변수 세팅 후 셸 진입

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

_header() {
    echo ""
    echo "  automator dev — $1"
    echo "  ────────────────────────────────────────"
}

_require_venv() {
    if [ ! -d "${VENV_DIR}" ]; then
        echo "  ❌ .venv 없음. 먼저 실행하세요: bash ./run/init.sh"
        exit 1
    fi
    source "${VENV_DIR}/bin/activate"
}

MODE="${1:---shell}"

if [ "${MODE}" = "--help" ] || [ "${MODE}" = "-h" ]; then
    cat << 'HELP'

  automator dev

  명령어:
    (없음)           가상환경 활성화 후 셸 진입
    --watch          파일 변경 시 unit 테스트 자동 재실행
    --session        네이버 로그인 후 session_state.json 저장
    --capture        셀렉터 캡처 도구 실행
    --factory-shell  factory 환경 셸 진입

  자주 쓰는 명령 (셸 진입 후):
    bash ./run/test.sh                  # unit 테스트
    bash ./run/test.sh --e2e            # e2e 포함
    bash ./run/test.sh --pipeline 1     # 파이프라인 1번
    bash ./run/factory.sh status        # 공장 현황
    bash ./run/factory.sh db-up         # DB 시작

HELP
    exit 0
fi

cd "${PROJECT_ROOT}"
_require_venv

_header "${MODE}"
echo "  Python : $(python --version)"
echo "  루트   : ${PROJECT_ROOT}"

case "${MODE}" in

  # ── 기본: 활성화된 셸로 진입 ─────────────────────────────────────────────
  --shell)
    echo ""
    echo "  자주 쓰는 명령:"
    echo "    bash ./run/test.sh                   # unit 테스트"
    echo "    bash ./run/test.sh --e2e             # e2e smoke 포함"
    echo "    bash ./run/test.sh --schedule        # 예약 발행 e2e"
    echo "    bash ./run/test.sh --pipeline 1      # 파이프라인 1번"
    echo "    bash ./run/test.sh --all             # 전체 테스트"
    echo ""
    echo "    bash ./run/factory.sh db-up          # MySQL 시작"
    echo "    bash ./run/factory.sh seed           # 조합 생성"
    echo "    bash ./run/factory.sh dispatch       # 배치 할당"
    echo "    bash ./run/factory.sh status         # 현황 확인"
    echo ""
    exec "${SHELL}"
    ;;

  # ── Watch: unit 테스트 자동 재실행 ──────────────────────────────────────
  --watch)
    echo ""
    echo "  automator/ 또는 tests/ 변경 시 unit 테스트 자동 실행"
    echo "  종료: Ctrl+C"
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
        echo "  (entr 사용 — pip install pytest-watch 으로 더 정교한 감지 가능)"
        echo ""
        find automator tests factory -name "*.py" | entr -c \
            pytest "${UNIT_TESTS[@]}" -m unit -v
    else
        echo "  ❌ pytest-watch 또는 entr 이 필요합니다."
        echo ""
        echo "     pip install pytest-watch   # 권장"
        echo "     brew install entr          # macOS 대안"
        exit 1
    fi
    ;;

  # ── Session: 네이버 로그인 후 세션 저장 ──────────────────────────────────
  --session)
    echo ""
    echo "  브라우저가 열리면 직접 네이버에 로그인하세요."
    echo "  로그인 완료 후 Enter 를 누르면 세션이 저장됩니다."
    echo ""

    if [ ! -f .env ]; then
        echo "  ❌ .env 없음. cp .env.example .env 후 NAVER_BLOG_ID 를 설정하세요."
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
    print(f"  브라우저에서 로그인을 완료하세요.")
    input("  완료 후 Enter 키를 누르세요... ")
    ctx.storage_state(path=session_path)
    browser.close()

print(f"  ✅ 세션 저장 완료: {session_path}")
PYEOF
    ;;

  # ── Capture: 셀렉터 캡처 도구 ────────────────────────────────────────────
  --capture)
    echo ""
    echo "  Chromium 을 열고 셀렉터를 캡처합니다."
    echo "  결과: selectors/naver/editor.json"
    echo ""

    if [ ! -f scripts/capture_selectors.py ]; then
        echo "  ❌ scripts/capture_selectors.py 없음"
        exit 1
    fi

    python scripts/capture_selectors.py
    ;;

  # ── Factory shell: factory 관련 셸 진입 ─────────────────────────────────
  --factory-shell)
    if [ ! -f factory/.env ]; then
        echo ""
        echo "  ⚠️  factory/.env 없음."
        echo "     cp factory/.env.example factory/.env"
        echo ""
    fi

    echo ""
    echo "  factory 환경 자주 쓰는 명령:"
    echo "    bash ./run/factory.sh db-up          # MySQL 시작"
    echo "    bash ./run/factory.sh seed           # 조합 생성"
    echo "    bash ./run/factory.sh dispatch       # 배치 할당"
    echo "    bash ./run/factory.sh run --dry-run  # 테스트 실행"
    echo "    bash ./run/factory.sh status         # 현황 확인"
    echo ""
    exec "${SHELL}"
    ;;

  *)
    echo ""
    echo "  알 수 없는 명령어: ${MODE}"
    echo "  도움말: bash ./run/dev.sh --help"
    exit 1
    ;;

esac
