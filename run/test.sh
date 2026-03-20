#!/usr/bin/env bash
# run/test.sh — 테스트 실행
#
# factory 테스트는 .env 의 TEST_DB_* 값으로 MySQL 컨테이너를 자동 기동한다.
# 테스트 종료 후 컨테이너는 자동 제거된다 (trap EXIT).
#
# 사용법:
#   bash ./run/test.sh               # unit 전체
#   bash ./run/test.sh --factory     # factory 단위 테스트 (MySQL 컨테이너 자동)
#   bash ./run/test.sh --e2e
#   bash ./run/test.sh --all
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

# ── venv 확인 ─────────────────────────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
    exit 1
fi
source "${VENV_DIR}/bin/activate"

# ── TEST_DB 설정 (.env 기본값) ────────────────────────────────────────────────
TEST_DB_HOST="${TEST_DB_HOST:-127.0.0.1}"
TEST_DB_PORT="${TEST_DB_PORT:-13306}"
TEST_DB_NAME="${TEST_DB_NAME:-automator_test}"
TEST_DB_USER="${TEST_DB_USER:-test}"
TEST_DB_PASSWORD="${TEST_DB_PASSWORD:-test}"
TEST_CONTAINER="automator_test_db"

export TEST_DB_URL="mysql+pymysql://${TEST_DB_USER}:${TEST_DB_PASSWORD}@${TEST_DB_HOST}:${TEST_DB_PORT}/${TEST_DB_NAME}?charset=utf8mb4"

# ── MySQL 컨테이너 헬퍼 ───────────────────────────────────────────────────────

_start_test_db() {
    echo "  MySQL 테스트 컨테이너 시작 중..."
    docker rm -f "${TEST_CONTAINER}" 2>/dev/null || true

    docker run -d \
        --name "${TEST_CONTAINER}" \
        -e MYSQL_DATABASE="${TEST_DB_NAME}" \
        -e MYSQL_USER="${TEST_DB_USER}" \
        -e MYSQL_PASSWORD="${TEST_DB_PASSWORD}" \
        -e MYSQL_ROOT_PASSWORD="root" \
        -p "${TEST_DB_HOST}:${TEST_DB_PORT}:3306" \
        mysql:8.0 \
        --character-set-server=utf8mb4 \
        --collation-server=utf8mb4_unicode_ci \
        > /dev/null

    echo -n "  DB 준비 대기 중"
    for i in $(seq 1 30); do
        if docker exec "${TEST_CONTAINER}" \
            mysqladmin ping -u root -proot -h 127.0.0.1 --silent 2>/dev/null; then
            echo " ✅"
            return
        fi
        echo -n "."; sleep 2
    done
    echo ""
    echo "❌ MySQL 컨테이너 시작 실패"
    docker logs "${TEST_CONTAINER}"
    exit 1
}

_stop_test_db() {
    echo ""
    echo "  MySQL 테스트 컨테이너 종료 중..."
    docker rm -f "${TEST_CONTAINER}" > /dev/null 2>&1 || true
    echo "  ✅ 컨테이너 제거 완료"
}

_run_factory_tests() {
    trap _stop_test_db EXIT
    _start_test_db
    echo ""
    echo "── factory unit ─────────────────────────"
    echo "  TEST_DB_URL=${TEST_DB_URL}"
    pytest factory/tests/ -v
}

# ── 모드 선택 ─────────────────────────────────────────────────────────────────

MODE="${1:---unit}"

case "${MODE}" in

  --unit)
    echo "── unit ─────────────────────────────────"
    pytest -m unit -v
    ;;

  --factory)
    _run_factory_tests
    ;;

  --e2e)
    echo "── [1/3] unit ───────────────────────────"
    pytest -m unit -v
    echo ""
    _run_factory_tests
    echo ""
    echo "── [3/3] e2e smoke ──────────────────────"
    pytest tests/test_e2e_naver.py -m "e2e and not slow" -v
    ;;

  --all)
    echo "── [1/3] unit ───────────────────────────"
    pytest -m unit -v
    echo ""
    _run_factory_tests
    echo ""
    echo "── [3/3] e2e ────────────────────────────"
    pytest tests/test_e2e_naver.py -m "e2e and not slow" -v
    ;;

  --help|-h)
    cat << 'HELP'

  bash ./run/test.sh               # unit tests
  bash ./run/test.sh --factory     # factory unit (MySQL container auto)
  bash ./run/test.sh --e2e         # unit + factory + e2e smoke
  bash ./run/test.sh --all         # everything

  Test files (tests/):
    test_post_step.py          PostStep.execute() self-dispatch
    test_smart_editor.py       SmartEditorOne DOM wiring
    test_title_generator.py    generate_title() + validate_template()
    test_paragraph_generator.py generate_paragraphs()
    test_image_processor.py    process_image() / process_featured()
    test_seo_prompt.py         build_prompt()
    test_block_handlers.py     BlockHandler image processing
    test_layout.py             Section/Block validation
    test_job_builder.py        PostingJob builder immutability
    test_job_validation.py     PostingJob.validate()
    test_job_execution.py      PostingJob.run() call sequence
    test_publish_option.py     PublishOption schedule
    test_seo_integration.py    SEO prompt in job context
    test_browser_actions.py    Pure DOM functions
    test_browser_config.py     BrowserSettings
    test_browser_selectors.py  SelectorLoader
    test_e2e_naver.py          E2E smoke (requires session)

HELP
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}"
    exit 1
    ;;

esac

echo ""
echo "✅ 완료"
