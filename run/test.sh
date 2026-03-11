#!/usr/bin/env bash
# run/test.sh
# -----------
# Activates the virtual environment and runs the test suite.
#
# Usage:
#   bash ./run/test.sh              # unit tests only (default, fast)
#   bash ./run/test.sh --e2e        # unit + e2e tests
#   bash ./run/test.sh --all        # unit + e2e + slow tests (includes publish)
#
# Options:
#   --unit   Run unit tests only (default)
#   --e2e    Run unit + e2e tests
#   --all    Run all tests including slow/publish tests

set -euo pipefail

# ── Resolve project root ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

# ── Guard: venv must exist ──────────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: .venv not found. Run setup first:"
    echo "  bash ./run/init.sh"
    exit 1
fi

# ── Activate virtual environment ────────────────────────────────────────────
source "${VENV_DIR}/bin/activate"

# ── Parse arguments ─────────────────────────────────────────────────────────
MODE="${1:---unit}"

echo "========================================"
echo "  automator — test runner"
echo "========================================"
echo ""

case "${MODE}" in

  --unit)
    echo "Mode : unit tests only (no browser)"
    echo ""
    pytest tests/test_blog_unit.py tests/test_config.py \
           -m unit \
           -v
    ;;

  --e2e)
    echo "Mode : unit + e2e tests (browser required)"
    echo ""
    # Run unit tests first — fail fast before launching a browser
    echo "--- [1/2] Unit tests ---"
    pytest tests/test_blog_unit.py tests/test_config.py \
           -m unit \
           -v

    echo ""
    echo "--- [2/2] E2E tests ---"
    pytest tests/test_blog_e2e.py \
           -m "e2e and not slow" \
           -v
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
    pytest tests/test_blog_unit.py tests/test_config.py \
           -m unit \
           -v

    echo ""
    echo "--- [2/3] E2E tests ---"
    pytest tests/test_blog_e2e.py \
           -m "e2e and not slow" \
           -v

    echo ""
    echo "--- [3/3] Slow/publish tests ---"
    pytest tests/test_blog_e2e.py \
           -m "e2e and slow" \
           -v
    ;;

  *)
    echo "Unknown option: ${MODE}"
    echo ""
    echo "Usage:"
    echo "  bash ./run/test.sh           # unit tests only (default)"
    echo "  bash ./run/test.sh --e2e     # unit + e2e tests"
    echo "  bash ./run/test.sh --all     # all tests including publish"
    exit 1
    ;;

esac

echo ""
echo "========================================"
echo "  All tests passed!"
echo "========================================"
