#!/usr/bin/env bash
# run/download_assets.sh
# ----------------------
# Google Fonts 에서 NotoSansKR (Regular 400) 를 다운로드해
# assets/fonts/NotoSansKR.ttf 로 저장한다.
#
# 한 번만 실행하면 됩니다.
#
# Usage:
#   bash ./run/download_assets.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
FONTS_DIR="${PROJECT_ROOT}/assets/fonts"
FONT_FILE="${FONTS_DIR}/NotoSansKR.ttf"

# ── 이미 있으면 건너뜀 ────────────────────────────────────────────────────────
if [ -f "${FONT_FILE}" ]; then
    echo "✅ 이미 존재: ${FONT_FILE}"
    exit 0
fi

mkdir -p "${FONTS_DIR}"

echo "  Google Fonts API 에서 CSS 조회 중..."

# ── Google Fonts API → CSS 응답 받기 ─────────────────────────────────────────
# User-Agent 를 브라우저로 설정해야 woff2 대신 ttf URL 이 포함된 CSS 를 반환함
CSS_URL="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400&display=swap"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

CSS=$(curl -fsSL --max-time 15 "${CSS_URL}" -H "User-Agent: ${UA}")

if [ -z "${CSS}" ]; then
    echo "❌ Google Fonts API 응답 없음. 네트워크를 확인하세요."
    exit 1
fi

# ── CSS 에서 ttf/woff2 URL 추출 ───────────────────────────────────────────────
# CSS 형식: src: url(https://fonts.gstatic.com/s/...ttf) format('truetype')
FONT_URL=$(echo "${CSS}" | grep -oP "https://fonts\.gstatic\.com/[^)']+" | grep -i "\.ttf\|\.woff2" | head -1)

# ttf 없으면 woff2 사용
if [ -z "${FONT_URL}" ]; then
    FONT_URL=$(echo "${CSS}" | grep -oP "https://fonts\.gstatic\.com/[^)']+" | head -1)
fi

if [ -z "${FONT_URL}" ]; then
    echo "❌ 폰트 URL 을 찾을 수 없습니다."
    echo "   CSS 응답:"
    echo "${CSS}" | head -20
    exit 1
fi

echo "  폰트 URL: ${FONT_URL}"
echo "  다운로드 중..."

curl -fsSL --max-time 30 "${FONT_URL}" -o "${FONT_FILE}"

SIZE=$(du -sh "${FONT_FILE}" | cut -f1)
echo ""
echo "✅ 폰트 저장 완료: ${FONT_FILE} (${SIZE})"
echo "   이미지 썸네일 텍스트에 자동으로 사용됩니다."
