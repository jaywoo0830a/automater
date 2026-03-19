#!/usr/bin/env bash
# run/factory.sh — DB 관리 및 스키마 초기화
#
#  DB 관리:
#    bash ./run/factory.sh db-up          MySQL 시작
#    bash ./run/factory.sh db-down        MySQL 종료
#    bash ./run/factory.sh db-reset       전체 초기화 (볼륨 삭제, 확인 필요)
#    bash ./run/factory.sh db-logs        MySQL 로그 실시간 확인
#
#  스키마:
#    bash ./run/factory.sh schema-init    ORM 모델 기반 테이블 생성 (IF NOT EXISTS)
#    bash ./run/factory.sh schema-drop    ORM 모델 기반 테이블 삭제 (확인 필요)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
COMPOSE_FILE="${PROJECT_ROOT}/factory/docker-compose.yml"

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
    echo ""
    echo "  다음 단계: bash ./run/factory.sh schema-init"
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
    echo "✅ DB 초기화 완료"
    echo ""
    echo "  다음 단계: bash ./run/factory.sh schema-init"
    ;;

  db-logs)
    docker compose -f "${COMPOSE_FILE}" logs -f db
    ;;

  # ── 스키마 관리 ─────────────────────────────────────────────────────────────

  schema-init)
    _require_venv
    _require_db
    echo "  ORM 모델 기반 스키마 생성 (CREATE TABLE IF NOT EXISTS)..."
    python -c "
from dotenv import load_dotenv; load_dotenv()
from factory.db import get_engine, create_schema
create_schema(get_engine())
print('  ✅ 스키마 생성 완료')
"
    ;;

  schema-drop)
    _require_venv
    _require_db
    echo "⚠️  모든 테이블이 삭제됩니다. 계속하려면 'yes' 입력:"
    read -r CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then echo "취소됨"; exit 0; fi
    python -c "
from dotenv import load_dotenv; load_dotenv()
from factory.db import get_engine, drop_schema
drop_schema(get_engine())
print('  ✅ 스키마 삭제 완료')
"
    ;;

  # ── 도움말 ─────────────────────────────────────────────────────────────────

  help|--help|-h)
    cat << 'HELP'

  DB 관리:
    bash ./run/factory.sh db-up           # MySQL 시작
    bash ./run/factory.sh db-down         # MySQL 종료
    bash ./run/factory.sh db-reset        # 전체 초기화 (확인 필요)
    bash ./run/factory.sh db-logs         # MySQL 로그

  스키마:
    bash ./run/factory.sh schema-init     # ORM 모델 기반 테이블 생성
    bash ./run/factory.sh schema-drop     # ORM 모델 기반 테이블 삭제

HELP
    ;;

  *)
    echo "알 수 없는 명령어: ${CMD}  (help 로 도움말 확인)"
    exit 1
    ;;

esac
