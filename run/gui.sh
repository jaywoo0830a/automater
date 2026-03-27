#!/usr/bin/env bash
# run/gui.sh — Campaign DSL Builder GUI
#
#   bash ./run/gui.sh
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

.venv/bin/python -m gui
