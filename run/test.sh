#!/usr/bin/env bash
# run/test.sh
# -----------
# Activates the virtual environment and runs the test suite.
#
# Usage:
#   bash ./run/test.sh                       # unit tests only (default, fast, no browser)
#   bash ./run/test.sh --e2e                 # unit + e2e smoke tests (browser required)
#   bash ./run/test.sh --schedule            # 예약 발행 UI e2e 테스트 (browser required)
#   bash ./run/test.sh --pipeline            # 4 pipeline scenarios (dry_run — no real post)
#   bash ./run/test.sh --pipeline <1-4>      # single pipeline scenario by number
#   bash ./run/test.sh --all                 # unit + e2e + schedule + pipeline (전체)
#
# Pipeline scenarios:
#   1  test_pipeline_full_layout   이미지+썸네일+단락 전체 레이아웃 (이미지 필요)
#   2  test_pipeline_text_only     텍스트 전용, 이미지 없음
#   3  test_pipeline_minimal       빈 레이아웃 (최소 경로)
#   4  test_pipeline_scheduled     예약 발행 fixed 흐름

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

PIPELINE_NAMES=(
    ""                             # index 0 — unused
    "test_pipeline_full_layout"    # 1
    "test_pipeline_text_only"      # 2
    "test_pipeline_minimal"        # 3
    "test_pipeline_scheduled"      # 4
)

_print_help() {
    echo "Usage:"
    echo "  bash ./run/test.sh                   # unit tests only (default)"
    echo "  bash ./run/test.sh --e2e             # unit + e2e smoke"
    echo "  bash ./run/test.sh --schedule        # 예약 발행 UI e2e 테스트"
    echo "  bash ./run/test.sh --pipeline        # all 4 pipeline scenarios"
    echo "  bash ./run/test.sh --pipeline <1-4>  # single scenario by number"
    echo "  bash ./run/test.sh --all             # unit + e2e + schedule + pipeline"
    echo ""
    echo "Pipeline scenarios:"
    for i in 1 2 3 4; do
        printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
    done
}

MODE="${1:---unit}"
PIPELINE_NUM="${2:-}"

if [ "${MODE}" = "--help" ] || [ "${MODE}" = "-h" ]; then
    _print_help
    exit 0
fi

cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: .venv not found. Run: bash ./run/init.sh"
    exit 1
fi

source "${VENV_DIR}/bin/activate"

UNIT_TESTS=(
    tests/test_job_unit.py
    tests/test_editor_unit.py
    tests/test_selector_unit.py
    tests/test_config.py
    tests/test_title_unit.py
    tests/test_layout_unit.py
    tests/test_paragraph_generator.py
)

echo "========================================"
echo "  automator — test runner"
echo "========================================"
echo ""

case "${MODE}" in

  --unit)
    echo "Mode : unit tests only (no browser)"
    echo ""
    pytest "${UNIT_TESTS[@]}" -m unit -v
    ;;

  --e2e)
    echo "Mode : unit + e2e smoke tests"
    echo ""
    echo "--- [1/2] Unit tests ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    echo ""
    echo "--- [2/2] E2E smoke tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v
    ;;

  --schedule)
    echo "Mode : 예약 발행 UI e2e 테스트 (dry_run=True)"
    echo ""
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s
    ;;

  --pipeline)
    if [ -n "${PIPELINE_NUM}" ]; then
      re='^[1-4]$'
      if ! [[ "${PIPELINE_NUM}" =~ $re ]]; then
        echo "ERROR: pipeline number must be 1–4 (got '${PIPELINE_NUM}')"
        echo ""
        for i in 1 2 3 4; do
          printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
        done
        exit 1
      fi
      TEST_NAME="${PIPELINE_NAMES[$PIPELINE_NUM]}"
      echo "Mode : pipeline ${PIPELINE_NUM}/4 — ${TEST_NAME}"
      echo ""
      pytest "tests/test_blog_e2e.py::${TEST_NAME}" -m "e2e and slow" -v -s
    else
      echo "Mode : all 4 pipeline scenarios (dry_run=True)"
      echo ""
      for i in 1 2 3 4; do
        printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
      done
      echo ""
      pytest tests/test_blog_e2e.py -m "e2e and slow" -v -s
    fi
    ;;

  --all)
    echo "Mode : all tests (unit + e2e smoke + schedule + pipeline)"
    echo ""
    echo "--- [1/4] Unit tests ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v

    echo ""
    echo "--- [2/4] E2E smoke tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v

    echo ""
    echo "--- [3/4] Schedule e2e tests ---"
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s

    echo ""
    echo "--- [4/4] Pipeline scenarios (1–4) ---"
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v -s
    ;;

  *)
    echo "Unknown option: ${MODE}"
    echo ""
    _print_help
    exit 1
    ;;

esac

echo ""
echo "========================================"
echo "  All tests passed!"
echo "========================================"
