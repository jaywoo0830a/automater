#!/usr/bin/env bash
# run/init.sh — 처음 한 번만 실행
#
# Uses uv to manage Python and the virtualenv:
#   - Installs uv if missing (~/.local/bin/uv)
#   - Downloads CPython 3.14.4 (via uv)
#   - Creates .venv from that Python
#   - Installs requirements + Playwright Chromium
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_VERSION="3.14.4"

cd "${PROJECT_ROOT}"

echo "========================================"
echo "  automator — 초기 환경 설정"
echo "========================================"
echo "  프로젝트 루트 : ${PROJECT_ROOT}"
echo "  Python        : ${PYTHON_VERSION}"
echo ""

# ── 0. uv 설치 확인 ─────────────────────────────────────────────────
export PATH="${HOME}/.local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1; then
    echo "  [0/5] uv 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "        ✅ 완료"
else
    echo "  [0/5] uv 확인됨 ($(uv --version))"
fi

# ── 1. Python 3.14 확보 ────────────────────────────────────────────
echo "  [1/5] CPython ${PYTHON_VERSION} 확보 중..."
uv python install "${PYTHON_VERSION}" 2>&1 | tail -1
echo "        ✅ 완료"

# ── 2. 가상환경 ────────────────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    current_ver="$("${VENV_DIR}/bin/python" --version 2>&1 | awk '{print $2}' || echo "")"
    if [ "${current_ver}" = "${PYTHON_VERSION}" ]; then
        echo "  [2/5] .venv 이미 존재 (Python ${current_ver}) — 건너뜀"
    else
        echo "  [2/5] .venv Python 버전 불일치 (${current_ver}) — 재생성"
        rm -rf "${VENV_DIR}"
        uv venv --python "${PYTHON_VERSION}" "${VENV_DIR}" 2>&1 | tail -1
        echo "        ✅ 완료"
    fi
else
    echo "  [2/5] 가상환경 생성 중..."
    uv venv --python "${PYTHON_VERSION}" "${VENV_DIR}" 2>&1 | tail -1
    echo "        ✅ 완료"
fi

# ── 3. 패키지 설치 ─────────────────────────────────────────────────
echo "  [3/5] 패키지 설치 중..."
uv pip install --python "${VENV_DIR}/bin/python" -r requirements.txt --quiet
echo "        ✅ 완료 ($("${VENV_DIR}/bin/python" --version))"

# ── 4. Playwright Chromium ─────────────────────────────────────────
echo "  [4/5] Playwright Chromium 설치 중..."
"${VENV_DIR}/bin/playwright" install chromium
echo "        ✅ 완료"

# ── 5. 디렉토리 ────────────────────────────────────────────────────
echo "  [5/5] 로그 디렉토리 준비..."
mkdir -p logs
echo "        ✅ 완료"

# ── .env ──────────────────────────────────────────────────────────
if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo ""
    echo "  [INFO] .env를 생성했습니다. 값을 채워주세요."
fi

echo ""
echo "========================================"
echo "  설정 완료"
echo "========================================"
echo ""
echo "  다음 단계:"
echo "    source .venv/bin/activate          # 가상환경 활성화"
echo "    bash ./run/test.sh                 # 테스트 실행"
echo "    bash ./run/test.sh --session       # 네이버 세션 준비"
echo "    bash ./run/gui.sh                  # GUI 실행"
echo ""
echo "  Tip: PATH에 uv를 영구 추가하려면 ~/.bashrc 또는 ~/.zshrc에:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
