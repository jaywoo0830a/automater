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
#   bash ./run/test.sh                 # unit 전체 (DB 불필요)
#   bash ./run/test.sh --integration   # integration/factory (MySQL 자동)
#   bash ./run/test.sh --e2e           # unit + integration + e2e smoke
#   bash ./run/test.sh --all           # everything
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

_run_integration_factory() {
    trap _stop_test_db EXIT
    _start_test_db
    echo ""
    echo "── integration/factory ─────────────────"
    echo "  TEST_DB_URL=${TEST_DB_URL}"
    pytest tests/integration/factory/ -v
}

# ── 모드 선택 ─────────────────────────────────────────────────────────────────

MODE="${1:---unit}"

case "${MODE}" in

  --unit)
    echo "── unit/automator ────────────────────────"
    pytest tests/unit/automator/ -v
    echo ""
    echo "── unit/factory ─────────────────────────"
    pytest tests/unit/factory/ -v
    echo ""
    echo "── integration/automator ────────────────"
    pytest tests/integration/automator/ -v
    echo ""
    echo "── browser ──────────────────────────────"
    pytest tests/browser/ -v
    ;;

  --integration)
    _run_integration_factory
    ;;

  --e2e)
    echo "── [1/3] unit + integration/automator + browser ──"
    pytest tests/unit/ tests/integration/automator/ tests/browser/ -v
    echo ""
    echo "── [2/3] integration/factory ─────────────"
    _run_integration_factory
    echo ""
    echo "── [3/3] e2e smoke ────────────────────────"
    pytest tests/e2e/ -m "e2e and not slow" -v
    ;;

  --all)
    echo "── [1/3] unit + integration/automator + browser ──"
    pytest tests/unit/ tests/integration/automator/ tests/browser/ -v
    echo ""
    echo "── [2/3] integration/factory ─────────────"
    _run_integration_factory
    echo ""
    echo "── [3/3] e2e ──────────────────────────────"
    pytest tests/e2e/ -v
    ;;

  --help|-h)
    cat << 'HELP'

  bash ./run/test.sh                 # unit (DB 불필요, 가장 빠름)
  bash ./run/test.sh --integration   # integration/factory (MySQL 자동)
  bash ./run/test.sh --e2e           # unit + integration + e2e smoke
  bash ./run/test.sh --all           # everything

  ── tests/unit/automator/            Automator 순수 단위 테스트
      test_title_generator.py         generate_title + validate_template
      test_paragraph_generator.py     generate_paragraphs stubs
      test_seo_prompt.py              build_prompt
      test_layout.py                  Section/Block validation
      test_post_step.py               PostStep.execute dispatch
      test_image_processor.py         process_image / process_featured
      test_ports.py                   Port ABCs + test doubles
      test_block_factory.py           block_type → Block + media_id resolution
      test_preset_loader.py           JSON config → frozen dataclass

  ── tests/unit/factory/              Factory 순수 단위 테스트 (DB 불필요)
      test_job_builder.py             Combination → PostingSpec 합성
      test_batch_worker.py            BatchWorker 실행 파이프라인
      test_storage.py                 LocalStorage 파일 작업
      test_bulk_importer.py           BulkImporter 입력 검증
      test_excel_parser.py            엑셀 파싱 + 헤더 해석
      test_affix_detector.py          접사 자동 감지

  ── tests/integration/automator/     Automator 통합 테스트
      test_spec_builder.py            PostingSpec immutability
      test_spec_validator.py          SpecValidator rules
      test_content_builder.py         ContentBuilder block → step
      test_runner.py                  JobRunner editor call sequence
      test_publish_option.py          Schedule resolution

  ── tests/integration/factory/       Factory 통합 테스트 (MySQL 필요)
      test_user.py                    User model + ownership
      test_preset_models.py           PostLayout/PublishPreset/RunPreset
      test_media.py                   Media model + ownership
      test_combo_generator.py         ComboGenerator slot logic
      test_keyword_picker.py          save_picks / load_picks
      test_batch_dispatcher.py        BatchDispatcher
      test_bulk_importer.py           BulkImporter full pipeline

  ── tests/browser/                   Playwright mocks (no real browser)
      test_smart_editor.py            SmartEditorOne DOM wiring
      test_browser_actions.py         Pure DOM functions
      test_browser_config.py          BrowserSettings
      test_browser_selectors.py       SelectorLoader

  ── tests/e2e/                       Real browser (requires session)
      test_e2e_naver.py               E2E smoke

HELP
    ;;

  *)
    echo "알 수 없는 옵션: ${MODE}"
    exit 1
    ;;

esac

echo ""
echo "✅ 완료"
