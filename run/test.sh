#!/usr/bin/env bash
# run/test.sh
# -----------
# Activates the virtual environment and runs the test suite.
#
# Usage:
#   bash ./run/test.sh              # unit tests only (default, fast)
#   bash ./run/test.sh --e2e        # unit + e2e tests
#   bash ./run/test.sh --all        # all tests including slow/publish

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

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
)

MODE="${1:---unit}"

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
    echo "Mode : unit + e2e tests (browser required)"
    echo ""
    echo "--- [1/2] Unit tests ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v

    echo ""
    echo "--- [2/2] E2E tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v
    ;;

  --all)
    echo "Mode : all tests including slow/publish (WARNING: may publish a post)"
    echo ""
    read -rp "This will run the publish test and create a real blog post. Continue? [y/N] " confirm
    if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi

    echo ""
    echo "--- [1/3] Unit tests ---"
    pytest "${UNIT_TESTS[@]}" -m unit -v

    echo ""
    echo "--- [2/3] E2E tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and not slow" -v

    echo ""
    echo "--- [3/3] Slow/publish tests ---"
    pytest tests/test_blog_e2e.py -m "e2e and slow" -v
    ;;

  *)
    echo "Unknown option: ${MODE}"
    echo "Usage:"
    echo "  bash ./run/test.sh           # unit tests only"
    echo "  bash ./run/test.sh --e2e     # unit + e2e"
    echo "  bash ./run/test.sh --all     # all including publish"
    exit 1
    ;;

esac

echo ""
echo "========================================"
echo "  All tests passed!"
echo "========================================"
