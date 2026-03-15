#!/usr/bin/env bash
# run/test.sh
# -----------
# Activates the virtual environment and runs the test suite.
#
# Usage:
#   bash ./run/test.sh                       # unit tests only (default, fast, no browser)
#   bash ./run/test.sh --e2e                 # unit + e2e smoke tests (browser required)
#   bash ./run/test.sh --schedule            # 예약 발행 UI e2e 테스트 (browser required)
#   bash ./run/test.sh --pipeline            # all 8 pipeline scenarios (dry_run — no real post)
#   bash ./run/test.sh --pipeline <1-8>      # single pipeline scenario by number
#   bash ./run/test.sh --all                 # unit + e2e + schedule + all pipeline tests
#
# Pipeline scenarios:
#   1  test_pipeline_default                 기본 (과외, full layout, 이미지×3+썸네일)
#   2  test_pipeline_hagwon                  학원, include_suffix=False
#   3  test_pipeline_salt_first              template="솔트+지역+과목+학습형태"
#   4  test_pipeline_fixed_title             fixed_title 직접 지정
#   5  test_pipeline_text_only               텍스트 전용 (이미지 없음)
#   6  test_pipeline_minimal                 빈 layout (최소)
#   7  test_pipeline_scheduled_fixed         예약 발행 — schedule_mode="fixed"
#   8  test_pipeline_scheduled_random_window 예약 발행 — schedule_mode="random_window"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

# ── Pipeline test name map (1-indexed) ──────────────────────────────────────
PIPELINE_NAMES=(
    ""                                         # index 0 — unused
    "test_pipeline_default"                    # 1
    "test_pipeline_hagwon"                     # 2
    "test_pipeline_salt_first"                 # 3
    "test_pipeline_fixed_title"                # 4
    "test_pipeline_text_only"                  # 5
    "test_pipeline_minimal"                    # 6
    "test_pipeline_scheduled_fixed"            # 7
    "test_pipeline_scheduled_random_window"    # 8
)

_print_help() {
    echo "Usage:"
    echo "  bash ./run/test.sh                   # unit tests only (default)"
    echo "  bash ./run/test.sh --e2e             # unit + e2e smoke"
    echo "  bash ./run/test.sh --schedule        # 예약 발행 UI e2e 테스트"
    echo "  bash ./run/test.sh --pipeline        # all 8 pipeline scenarios"
    echo "  bash ./run/test.sh --pipeline <1-8>  # single scenario by number"
    echo "  bash ./run/test.sh --all             # unit + e2e + schedule + all pipelines"
    echo ""
    echo "Pipeline scenarios:"
    for i in 1 2 3 4 5 6 7 8; do
        printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
    done
    echo ""
    echo "Schedule e2e tests (tests/test_schedule_e2e.py):"
    echo "  test_popover_opens_with_now_selected_by_default"
    echo "  test_scheduled_radio_is_selected_after_set"
    echo "  test_hour_select_matches_schedule_at"
    echo "  test_minute_select_matches_floored_schedule_at"
    echo "  test_full_schedule_state_via_publish"
    echo "  test_schedule_via_job_fixed_mode"
    echo "  test_schedule_via_job_random_window_mode"
}

MODE="${1:---unit}"
PIPELINE_NUM="${2:-}"

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

# ── Unit test files ──────────────────────────────────────────────────────────
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
    echo "Mode : unit + e2e smoke tests (schedule 제외)"
    echo ""
    echo "--- [1/2] Unit tests ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v
    echo ""
    echo "--- [2/2] E2E smoke tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v
    ;;

  --schedule)
    echo "Mode : 예약 발행 UI e2e 테스트 (dry_run=True — 실제 발행 없음)"
    echo ""
    echo "Tests:"
    echo "  · popover 기본값(현재) 확인"
    echo "  · 예약 라디오 선택 확인"
    echo "  · 시/분 select 값 확인"
    echo "  · fixed / random_window 전체 흐름 확인"
    echo ""
    pytest tests/test_schedule_e2e.py -m "e2e" -v -s
    ;;

  --pipeline)
    if [ -n "${PIPELINE_NUM}" ]; then
      re='^[1-8]$'
      if ! [[ "${PIPELINE_NUM}" =~ $re ]]; then
        echo "ERROR: pipeline number must be 1–8 (got '${PIPELINE_NUM}')"
        echo ""
        for i in 1 2 3 4 5 6 7 8; do
          printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
        done
        exit 1
      fi
      TEST_NAME="${PIPELINE_NAMES[$PIPELINE_NUM]}"
      echo "Mode : pipeline scenario ${PIPELINE_NUM}/8 — ${TEST_NAME}"
      echo "       (dry_run=True — 실제 발행 없음)"
      echo ""
      pytest "tests/test_blog_e2e.py::${TEST_NAME}" -m "e2e and slow" -v -s
    else
      echo "Mode : all 8 pipeline scenarios (dry_run=True — 실제 발행 없음)"
      echo ""
      for i in 1 2 3 4 5 6 7 8; do
        printf "  %d  %s\n" "$i" "${PIPELINE_NAMES[$i]}"
      done
      echo ""
      pytest tests/test_blog_e2e.py -m "e2e and slow" -v -s
    fi
    ;;

  --all)
    echo "Mode : all tests (unit + e2e + schedule + pipeline, dry_run=True)"
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
    echo "--- [4/4] Pipeline scenarios (1–8) ---"
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
