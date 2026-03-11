#!/usr/bin/env bash
# run/init.sh
# -----------
# Sets up the virtual environment, installs dependencies,
# and installs the Playwright Chromium browser.
#
# Usage:
#   bash ./run/init.sh

set -euo pipefail

# ── Resolve project root (one level up from this script) ───────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

echo "========================================"
echo "  automator — environment setup"
echo "========================================"
echo "Project root : ${PROJECT_ROOT}"
echo "Virtual env  : ${VENV_DIR}"
echo ""

# ── 1. Create virtual environment ──────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    echo "[1/4] .venv already exists — skipping creation"
else
    echo "[1/4] Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
    echo "      ✓ .venv created"
fi

# ── 2. Activate virtual environment ────────────────────────────────────────
echo "[2/4] Activating virtual environment..."
source "${VENV_DIR}/bin/activate"
echo "      ✓ activated ($(python --version))"

# ── 3. Install Python dependencies ─────────────────────────────────────────
echo "[3/4] Installing dependencies from requirements.txt..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "      ✓ dependencies installed"

# ── 4. Install Playwright browser ──────────────────────────────────────────
echo "[4/4] Installing Playwright Chromium browser..."
playwright install chromium
echo "      ✓ Chromium installed"

# ── Done ───────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and fill in your credentials"
echo "     cp .env.example .env"
echo ""
echo "  2. Fill in .env with your Naver credentials"
echo "  3. Run the tests:"
echo "     bash ./run/test.sh"
