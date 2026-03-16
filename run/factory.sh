#!/usr/bin/env bash
# run/factory.sh — 공장 파이프라인
#
#  처음 시작:
#    bash ./run/factory.sh db-up
#    bash ./run/factory.sh seed
#    bash ./run/factory.sh dispatch [--schedule-at "2026-03-25 09:00"]
#    bash ./run/factory.sh run [--workers 5] [--dry-run]
#
#  DB 관리:
#    db-up      MySQL 시작
#    db-down    MySQL 종료
#    db-reset   데이터 전체 삭제 후 재초기화 (볼륨 삭제, 확인 필요)
#    db-logs    MySQL 로그 실시간 확인
#
#  파이프라인:
#    seed       조합 생성 (멱등 — 재실행 안전)
#    dispatch   가용 계정에 배치 할당
#    run        pending 배치 병렬 실행
#    status     현재 현황 요약
#    logs       factory.log 실시간 확인
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
COMPOSE_FILE="${PROJECT_ROOT}/factory/docker-compose.yml"
LOG_FILE="${PROJECT_ROOT}/logs/factory.log"

_require_venv() {
    if [ ! -d "${VENV_DIR}" ]; then
        echo "❌ .venv 없음 — bash ./run/init.sh 먼저 실행하세요"
        exit 1
    fi
    source "${VENV_DIR}/bin/activate"
}

_require_db() {
    if ! docker compose -f "${COMPOSE_FILE}" exec -T db \
        mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo "⚠️  MySQL 이 실행 중이지 않습니다 — bash ./run/factory.sh db-up"
        exit 1
    fi
}

_db_wait() {
    local max="${1:-12}"
    echo "  DB 준비 대기 중..."
    for i in $(seq 1 "${max}"); do
        if docker compose -f "${COMPOSE_FILE}" exec -T db \
            mysqladmin ping -h localhost --silent 2>/dev/null; then
            return 0
        fi
        sleep 2
    done
    echo "❌ DB 준비 타임아웃"
    exit 1
}

CMD="${1:-help}"
shift || true
cd "${PROJECT_ROOT}"

case "${CMD}" in

  # ── DB 관리 ────────────────────────────────────────────────────────────────

  db-up)
    docker compose -f "${COMPOSE_FILE}" up -d
    _db_wait 12
    echo "✅ MySQL 준비 완료 (localhost:3306)"
    ;;

  db-down)
    docker compose -f "${COMPOSE_FILE}" down
    echo "✅ 종료 완료"
    ;;

  db-reset)
    echo "⚠️  모든 데이터가 삭제됩니다. 계속하려면 'yes' 입력:"
    read -r CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then echo "취소됨"; exit 0; fi
    docker compose -f "${COMPOSE_FILE}" down -v
    docker compose -f "${COMPOSE_FILE}" up -d
    _db_wait 18
    echo "✅ 초기화 완료 — 스키마·시드 자동 적용됨"
    ;;

  db-logs)
    docker compose -f "${COMPOSE_FILE}" logs -f db
    ;;

  # ── 파이프라인 ─────────────────────────────────────────────────────────────

  seed)
    _require_venv
    _require_db
    echo "조합 생성: 선택된 값들의 카테시안 곱 → combinations 테이블"
    python -m factory.main seed "$@"
    ;;

  select)
    _require_venv
    _require_db
    python -m factory.main select "$@"
    ;;

  dispatch)
    _require_venv
    _require_db
    echo "배치 할당: 가용 계정에 조합 40개씩 배분"
    python -m factory.main dispatch "$@"
    ;;

  run)
    _require_venv
    _require_db
    echo "배치 실행: pending 배치 병렬 처리"
    python -m factory.main run "$@"
    ;;

  status)
    _require_venv
    _require_db
    python -m factory.main status
    ;;

  logs)
    if [ ! -f "${LOG_FILE}" ]; then
        echo "❌ 로그 파일 없음: ${LOG_FILE}"
        echo "   run 명령을 먼저 실행하세요."
        exit 1
    fi
    tail -f "${LOG_FILE}"
    ;;

  # ── 도움말 ─────────────────────────────────────────────────────────────────

  help|--help|-h)
    cat << 'HELP'

  DB 관리:
    bash ./run/factory.sh db-up
    bash ./run/factory.sh db-down
    bash ./run/factory.sh db-reset          # 전체 초기화 (확인 필요)
    bash ./run/factory.sh db-logs           # MySQL 로그

  파이프라인:
    bash ./run/factory.sh select --list
    bash ./run/factory.sh select --dimension region --values "강남구,수원시"
    bash ./run/factory.sh select --dimension subject --values "수학"
    bash ./run/factory.sh select --dimension learning_type --values "과외"
    bash ./run/factory.sh seed
    bash ./run/factory.sh dispatch [--schedule-at "YYYY-MM-DD HH:MM"]
    bash ./run/factory.sh run [--workers N] [--dry-run]
    bash ./run/factory.sh status
    bash ./run/factory.sh logs              # factory.log 실시간 확인

HELP
    ;;

  *)
    echo "알 수 없는 명령어: ${CMD}  (help 로 도움말 확인)"
    exit 1
    ;;

esac
