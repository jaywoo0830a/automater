#!/usr/bin/env bash
# run/seed.sh — DB 초기화 + 지역 데이터 시딩
#
# 실행 순서
#   1. Docker DB 시작 (이미 실행 중이면 건너뜀)
#   2. 스키마 + 기본 시드 데이터 적용 (seed.sql)
#   3. 지역 데이터 자동 수집 및 시딩 (build_region_seed.py)
#   4. 조합 생성 (combinations 테이블)
#
# 옵션
#   --sido 서울 경기 부산   특정 시도만 시딩 (기본: 서울 경기)
#   --all                  전국 전체 시딩
#   --no-dong              읍면동 제외 (시군구까지만)
#   --no-gps               GPS 좌표 조회 생략 (KAKAO_REST_API_KEY 없을 때)
#   --skip-region          지역 수집 생략 (기존 seed_regions.sql 재사용)
#   --skip-combo           조합 생성 생략
#
# Usage:
#   bash ./run/seed.sh                         # 서울·경기 기본
#   bash ./run/seed.sh --all --no-dong         # 전국 시군구까지
#   bash ./run/seed.sh --all                   # 전국 전체 (오래 걸림)
#   bash ./run/seed.sh --skip-region           # 지역 재수집 생략
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
COMPOSE_FILE="${PROJECT_ROOT}/factory/docker-compose.yml"

cd "${PROJECT_ROOT}"

# ── 환경변수 로드 ─────────────────────────────────────────────────────────────
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -o allexport
    source "${PROJECT_ROOT}/.env"
    set +o allexport
fi
if [ -f "${PROJECT_ROOT}/factory/.env" ]; then
    set -o allexport
    source "${PROJECT_ROOT}/factory/.env"
    set +o allexport
fi

# ── 인자 파싱 ─────────────────────────────────────────────────────────────────
REGION_ARGS=()
SKIP_REGION=false
SKIP_COMBO=false
SIDO_LIST=()
ALL_SIDO=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)         ALL_SIDO=true;          shift ;;
        --no-dong)     REGION_ARGS+=(--no-dong); shift ;;
        --no-gps)      REGION_ARGS+=(--no-gps);  shift ;;
        --skip-region) SKIP_REGION=true;       shift ;;
        --skip-combo)  SKIP_COMBO=true;        shift ;;
        --sido)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                SIDO_LIST+=("$1"); shift
            done
            ;;
        *) echo "알 수 없는 옵션: $1"; exit 1 ;;
    esac
done

# 기본값: 서울·경기
if [ ${#SIDO_LIST[@]} -eq 0 ] && [ "${ALL_SIDO}" = false ]; then
    SIDO_LIST=("서울" "경기")
fi

# ── venv 확인 ─────────────────────────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
    exit 1
fi
source "${VENV_DIR}/bin/activate"

echo "========================================"
echo "  automator — 시딩"
echo "========================================"

# ── 1. DB 시작 ────────────────────────────────────────────────────────────────
echo ""
echo "── [1/4] DB 시작 ────────────────────────────────────────"

if docker compose -f "${COMPOSE_FILE}" ps --status running 2>/dev/null | grep -q "db"; then
    echo "  ✅ DB 이미 실행 중"
else
    echo "  Docker DB 시작 중..."
    docker compose -f "${COMPOSE_FILE}" up -d
    echo "  연결 대기 중..."
    for i in $(seq 1 18); do
        if docker compose -f "${COMPOSE_FILE}" exec -T db \
           mysqladmin ping -h localhost --silent 2>/dev/null; then
            echo "  ✅ DB 준비 완료"
            break
        fi
        if [ "${i}" -eq 18 ]; then
            echo "  ❌ DB 연결 실패 (${i}번 시도)"
            exit 1
        fi
        sleep 5
    done
fi

# ── 2. 스키마 + 기본 시드 ────────────────────────────────────────────────────
echo ""
echo "── [2/4] 스키마 + 기본 시드 적용 ───────────────────────"
python -m factory.main db-init 2>/dev/null || true

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-automator}"
DB_USER="${DB_USER:-automator}"
DB_PASSWORD="${DB_PASSWORD:-automatorpass}"

_mysql() {
    mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" \
          -p"${DB_PASSWORD}" "${DB_NAME}" "$@"
}

echo "  스키마 적용 중..."
_mysql < factory/schema.sql
echo "  기본 시드 적용 중..."
_mysql < factory/seed.sql
echo "  ✅ 완료"

# ── 3. 지역 데이터 수집 + 시딩 ───────────────────────────────────────────────
echo ""
echo "── [3/4] 지역 데이터 시딩 ──────────────────────────────"

if [ "${SKIP_REGION}" = true ]; then
    echo "  --skip-region: 기존 seed_regions.sql 재사용"
    if [ -f "factory/seed_regions.sql" ]; then
        _mysql < factory/seed_regions.sql
        echo "  ✅ seed_regions.sql 적용 완료"
    else
        echo "  ⚠️  factory/seed_regions.sql 없음 — 지역 시딩 생략"
    fi
else
    if [ "${ALL_SIDO}" = true ]; then
        echo "  전국 지역 수집 중 (시간이 걸립니다)..."
        python scripts/build_region_seed.py --all "${REGION_ARGS[@]}"
    else
        echo "  시도 수집: ${SIDO_LIST[*]}"
        python scripts/build_region_seed.py --sido "${SIDO_LIST[@]}" "${REGION_ARGS[@]}"
    fi

    if [ -f "factory/seed_regions.sql" ]; then
        echo "  DB 적용 중..."
        _mysql < factory/seed_regions.sql
        echo "  ✅ 지역 시딩 완료"
    else
        echo "  ❌ seed_regions.sql 생성 실패"
        exit 1
    fi
fi

# ── 4. 조합 생성 ─────────────────────────────────────────────────────────────
echo ""
echo "── [4/4] 조합 생성 ─────────────────────────────────────"

if [ "${SKIP_COMBO}" = true ]; then
    echo "  --skip-combo: 조합 생성 생략"
else
    python -m factory.main seed
    echo "  ✅ 조합 생성 완료"
fi

echo ""
echo "========================================"
echo "  시딩 완료"
echo "========================================"
echo ""
echo "  다음 단계:"
echo "    bash ./run/test.sh --pipeline   # 파이프라인 테스트 (dry_run)"
echo "    bash ./run/test.sh --real-run   # 실제 발행 테스트"
echo "    bash ./run/factory.sh dispatch  # 배치 생성"
echo "    bash ./run/factory.sh run       # 포스팅 시작"
echo ""
