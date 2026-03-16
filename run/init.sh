#!/usr/bin/env bash
# run/init.sh — 처음 한 번만 실행
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

echo "========================================"
echo "  automator — 초기 환경 설정"
echo "========================================"
echo "  프로젝트 루트 : ${PROJECT_ROOT}"
echo ""

# 1. 가상환경
if [ -d "${VENV_DIR}" ]; then
    echo "  [1/4] .venv 이미 존재 — 건너뜀"
else
    echo "  [1/4] 가상환경 생성 중..."
    python3 -m venv "${VENV_DIR}"
    echo "        ✅ 완료"
fi

# 2. 활성화
source "${VENV_DIR}/bin/activate"
echo "  [2/4] 가상환경 활성화 ($(python --version))"

# 3. 패키지 설치
echo "  [3/4] 패키지 설치 중..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "        ✅ 완료"

# 4. Playwright Chromium
echo "  [4/4] Playwright Chromium 설치 중..."
playwright install chromium
echo "        ✅ 완료"

# 로그 디렉토리 생성
mkdir -p logs

echo ""
echo "========================================"
echo "  설정 완료"
echo "========================================"
echo ""
echo "  다음 단계:"
echo "    cp .env.example .env              # 환경 파일 설정"
echo "    bash ./run/download_fonts.sh      # 한글 폰트 다운로드 (썸네일용)"
echo "    bash ./run/test.sh                # 단위 테스트로 설치 확인"
echo "    bash ./run/dev.sh --session       # 네이버 세션 저장"
echo ""
echo "  공장 파이프라인:"
echo "    cp factory/.env.example factory/.env"
echo "    bash ./run/factory.sh db-up"
echo "    bash ./run/factory.sh seed"
echo ""
