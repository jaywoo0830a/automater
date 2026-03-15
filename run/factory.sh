#!/usr/bin/env bash
# run/factory.sh
# --------------
# 공장 파이프라인 — 대량 포스팅 자동화
#
# ┌─────────────────────────────────────────────────────────────────┐
# │  처음 시작할 때 순서                                             │
# │                                                                 │
# │  1. bash ./run/factory.sh db-up        DB 컨테이너 시작         │
# │  2. bash ./run/factory.sh seed         조합 생성 (1회만)        │
# │  3. bash ./run/factory.sh dispatch     계정에 배치 할당         │
# │  4. bash ./run/factory.sh run          병렬 실행                │
# │                                                                 │
# │  한 번에:  bash ./run/factory.sh all                            │
# └─────────────────────────────────────────────────────────────────┘

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
COMPOSE_FILE="${PROJECT_ROOT}/factory/docker-compose.yml"

_header() {
    echo ""
    echo "  automator factory — $1"
    echo "  ────────────────────────────────────────"
}

_done() { echo "  ✅  $1"; }

_fail() { echo "  ❌  $1" >&2; exit 1; }

_require_venv() {
    if [ ! -d "${VENV_DIR}" ]; then
        _fail ".venv 없음. 먼저 실행하세요: bash ./run/init.sh"
    fi
    source "${VENV_DIR}/bin/activate"
}

_require_db() {
    if ! docker compose -f "${COMPOSE_FILE}" exec -T db \
        mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo ""
        echo "  ⚠️   MySQL이 실행 중이지 않습니다."
        echo "       다음 명령으로 시작하세요:"
        echo "         bash ./run/factory.sh db-up"
        echo ""
        exit 1
    fi
}

CMD="${1:-help}"
shift || true

cd "${PROJECT_ROOT}"

case "${CMD}" in

  db-up)
    _header "MySQL 시작"
    docker compose -f "${COMPOSE_FILE}" up -d
    echo ""
    echo "  DB 준비 대기 중..."
    for i in $(seq 1 12); do
        if docker compose -f "${COMPOSE_FILE}" exec -T db \
            mysqladmin ping -h localhost --silent 2>/dev/null; then
            break
        fi
        sleep 2
    done
    _done "MySQL 준비 완료 (localhost:3306)"
    ;;

  db-down)
    _header "MySQL 종료"
    docker compose -f "${COMPOSE_FILE}" down
    _done "종료 완료"
    ;;

  db-reset)
    _header "MySQL 초기화 (데이터 전체 삭제 후 재생성)"
    echo ""
    echo "  ⚠️   모든 데이터가 삭제됩니다. 계속하려면 'yes' 를 입력하세요."
    read -r CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
        echo "  취소됐습니다."
        exit 0
    fi
    echo ""
    echo "  컨테이너 및 볼륨 삭제 중..."
    docker compose -f "${COMPOSE_FILE}" down -v
    echo "  컨테이너 재시작 중..."
    docker compose -f "${COMPOSE_FILE}" up -d
    echo ""
    echo "  DB 준비 대기 중... (스키마·시드 자동 적용)"
    for i in $(seq 1 18); do
        if docker compose -f "${COMPOSE_FILE}" exec -T db \
            mysqladmin ping -h localhost --silent 2>/dev/null; then
            break
        fi
        sleep 2
    done
    _done "초기화 완료 — 스키마·시드 적용됨 (localhost:3306)"
    ;;

  db-logs)
    docker compose -f "${COMPOSE_FILE}" logs -f db
    ;;

  seed)
    _header "조합 생성 (seed)"
    echo "  지역 × 과목 × 학습형태 × 띄어쓰기 × 접미사 → combinations 테이블"
    echo ""
    _require_venv
    _require_db
    python -m factory.main seed "$@"
    ;;

  dispatch)
    _header "배치 할당 (dispatch)"
    echo "  가용 계정에 미사용 조합 40개씩 배분합니다."
    echo ""
    _require_venv
    _require_db
    python -m factory.main dispatch "$@"
    ;;

  run)
    _header "배치 실행 (run)"
    echo "  pending 배치를 병렬로 실행합니다."
    echo ""
    _require_venv
    _require_db
    python -m factory.main run "$@"
    ;;

  status)
    _header "현황 확인"
    _require_venv
    _require_db
    python -m factory.main status
    ;;

  all)
    _header "전체 실행 (seed → dispatch → run)"
    _require_venv
    _require_db
    echo "  [1/3] seed"
    python -m factory.main seed
    echo ""
    echo "  [2/3] dispatch"
    python -m factory.main dispatch "$@"
    echo ""
    echo "  [3/3] run"
    python -m factory.main run "$@"
    ;;

  help|--help|-h)
    cat << 'HELP'

  automator factory

  처음 시작할 때:
    bash ./run/factory.sh db-up
    bash ./run/factory.sh seed
    bash ./run/factory.sh dispatch
    bash ./run/factory.sh run

  한 번에:
    bash ./run/factory.sh all

  ────────────────────────────────────────
  명령어

  db-up                  MySQL 컨테이너 시작
  db-down                MySQL 컨테이너 종료
  db-reset               데이터 전체 삭제 후 재초기화 (볼륨 삭제)
  db-logs                MySQL 로그 실시간 확인

  seed                   조합 테이블 채우기 (멱등)
  dispatch               계정에 배치 할당
    --schedule-at TIME     예약 시각 (예: "2026-03-25 09:00")
  run                    pending 배치 실행
    --workers N            병렬 브라우저 수 (기본값: 5)
    --dry-run              실제 발행 없이 UI 흐름만
  status                 현재 진행 상황 요약

  all                    seed + dispatch + run 순서로 실행
    (dispatch/run 옵션 그대로 전달됨)

HELP
    ;;

  *)
    echo ""
    echo "  알 수 없는 명령어: ${CMD}"
    echo "  도움말: bash ./run/factory.sh help"
    exit 1
    ;;

esac
