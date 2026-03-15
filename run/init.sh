#!/usr/bin/env bash
# run/init.sh
# -----------
# 처음 한 번만 실행. 가상환경 생성 + 의존성 설치 + Playwright Chromium 설치.
#
# Usage:
#   bash ./run/init.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

echo "========================================"
echo "  automator — 초기 환경 설정"
echo "========================================"
echo "  프로젝트 루트 : ${PROJECT_ROOT}"
echo "  가상환경      : ${VENV_DIR}"
echo ""

# ── 1. 가상환경 생성 ─────────────────────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    echo "  [1/4] .venv 이미 존재 — 건너뜀"
else
    echo "  [1/4] 가상환경 생성 중..."
    python3 -m venv "${VENV_DIR}"
    echo "        ✅ .venv 생성 완료"
fi

# ── 2. 가상환경 활성화 ───────────────────────────────────────────────────────
echo "  [2/4] 가상환경 활성화..."
source "${VENV_DIR}/bin/activate"
echo "        ✅ 활성화 완료 ($(python --version))"

# ── 3. Python 패키지 설치 ────────────────────────────────────────────────────
echo "  [3/4] Python 패키지 설치 중... (requirements.txt)"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "        ✅ 패키지 설치 완료"

# ── 4. Playwright Chromium 설치 ─────────────────────────────────────────────
echo "  [4/4] Playwright Chromium 설치 중..."
playwright install chromium
echo "        ✅ Chromium 설치 완료"

# ── 완료 ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  설정 완료!"
echo "========================================"
echo ""
echo "  다음 단계:"
echo ""
echo "  1. 환경 파일 설정"
echo "       cp .env.example .env"
echo "       # .env 에 Naver 계정 정보 입력"
echo ""
echo "  2. 단위 테스트로 설치 확인"
echo "       bash ./run/test.sh"
echo ""
echo "  3. 네이버 세션 저장 (브라우저 로그인)"
echo "       bash ./run/dev.sh --session"
echo ""
echo "  4. (공장 파이프라인) DB 시작 및 초기화"
echo "       cp factory/.env.example factory/.env"
echo "       bash ./run/factory.sh db-up"
echo "       bash ./run/factory.sh seed"
echo ""
