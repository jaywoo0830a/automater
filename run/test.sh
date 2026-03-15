#!/usr/bin/env bash
# run/test.sh
# -----------
# 테스트 실행.
#
# 명령어:
#   (없음)             unit 테스트만 (빠름, 브라우저 불필요)
#   --e2e              unit + e2e smoke 테스트
#   --schedule         예약 발행 UI e2e 테스트
#   --pipeline         파이프라인 4개 시나리오 전체
#   --pipeline <1-4>   파이프라인 단일 시나리오
#   --factory          factory 단위 테스트 (DB 불필요)
#   --all              전체 (unit + e2e + schedule + pipeline)
#
# 파이프라인 시나리오:
#   1  full_layout    이미지+썸네일+단락 전체 (이미지 필요)
#   2  text_only      텍스트 전용
#   3  minimal        빈 레이아웃 (최소 경로)
#   4  scheduled      예약 발행 fixed 흐름

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

PIPELINE_NAMES=(
    ""
    "test_pipeline_full_layout"
    "test_pipeline_text_only"
    "test_pipeline_minimal"
    "test_pipeline_scheduled"
)

UNIT_TESTS=(
    tests/test_job_unit.py
    tests/test_editor_unit.py
    tests/test_selector_unit.py
    tests/test_config.py
    tests/test_title_unit.py
    tests/test_layout_unit.py
    tests/test_paragraph_generator.py
)

FACTORY_TESTS=(
    factory/tests/test_combo_generator.py
    factory/tests/test_dispatcher.py
)

_header() {
    echo ""
    echo "  automator test — $1"
    echo "  ────────────────────────────────────────"
}

_print_help() {
    cat << 'HELP'

  automator test runner

  명령어:
    (없음)             unit 테스트만 (빠름, 브라우저 불필요)
    --e2e              unit + e2e smoke
    --schedule         예약 발행 UI e2e
    --pipeline         파이프라인 4개 전체
    --pipeline <1-4>   파이프라인 단일 시나리오
    --factory          factory 단위 테스트
    --all              전체 (unit + e2e + schedule + pipeline)

  파이프라인 시나리오:
    1  full_layout    이미지+썸네일+단락 전체 (이미지 필요)
    2  text_only      텍스트 전용
    3  minimal        빈 레이아웃 최소 경로
    4  scheduled      예약 발행 fixed 흐름

HELP
}

MODE="${1:---unit}"
PIPELINE_NUM="${2:-}"

if [ "${MODE}" = "--help" ] || [ "${MODE}" = "-h" ]; then
    _print_help
    exit 0
fi

cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "  ❌ .venv 없음. 먼저 실행하세요: bash ./run/init.sh"
    exit 1
fi

source "${VENV_DIR}/bin/activate"

echo "========================================"
echo "  automator — test runner"
echo "========================================"

case "${MODE}" in

  --unit)
    _header "unit 테스트 (브라우저 없음)"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    ;;

  --e2e)
    _header "unit + e2e smoke"
    echo ""
    echo "  --- [1/2] unit ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    echo ""
    echo "  --- [2/2] e2e smoke ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v
    ;;

  --schedule)
    _header "예약 발행 UI e2e (dry_run=True)"
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s
    ;;

  --pipeline)
    if [ -n "${PIPELINE_NUM}" ]; then
        re='^[1-4]$'
        if ! [[ "${PIPELINE_NUM}" =~ $re ]]; then
            echo "  ❌ 1–4 사이 숫자를 입력하세요 (입력값: '${PIPELINE_NUM}')"
            echo ""
            for i in 1 2 3 4; do
                printf "     %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
            done
            exit 1
        fi
        TEST_NAME="${PIPELINE_NAMES[$PIPELINE_NUM]}"
        _header "pipeline ${PIPELINE_NUM}/4 — ${TEST_NAME}"
        pytest "tests/test_blog_e2e.py::${TEST_NAME}" -m "e2e and slow" -v -s
    else
        _header "pipeline 전체 (1–4)"
        echo ""
        for i in 1 2 3 4; do
            printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
        done
        echo ""
        pytest tests/test_blog_e2e.py -m "e2e and slow" -v -s
    fi
    ;;

  --factory)
    _header "factory 단위 테스트 (DB 불필요)"
    pytest "${FACTORY_TESTS[@]}" -v
    ;;

  --all)
    _header "전체 테스트"
    echo ""
    echo "  --- [1/5] unit ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v

    echo ""
    echo "  --- [2/5] factory unit ---"
    pytest "${FACTORY_TESTS[@]}" -v

    echo ""
    echo "  --- [3/5] e2e smoke ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v

    echo ""
    echo "  --- [4/5] schedule e2e ---"
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s

    echo ""
    echo "  --- [5/5] pipeline (1–4) ---"
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v -s
    ;;

  *)
    echo "  알 수 없는 옵션: ${MODE}"
    echo ""
    _print_help
    exit 1
    ;;

esac

echo ""
echo "========================================"
echo "  ✅ 테스트 완료"
echo "========================================"
