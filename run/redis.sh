#!/usr/bin/env bash
# run/redis.sh — Redis 세션 저장소 관리
#
# 사용법:
#   bash ./run/redis.sh          # 시작
#   bash ./run/redis.sh stop     # 종료
#   bash ./run/redis.sh status   # 상태 확인
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

MODE="${1:-start}"

case "${MODE}" in

  start)
    echo "Redis 시작 중..."
    docker compose up -d redis
    echo "✅ Redis 실행 중 (localhost:6379)"
    ;;

  stop)
    echo "Redis 종료 중..."
    docker compose down
    echo "✅ 종료 완료"
    ;;

  status)
    if docker compose ps redis 2>/dev/null | grep -q "running"; then
      echo "✅ Redis 실행 중"
      docker compose exec redis redis-cli ping
    else
      echo "❌ Redis 꺼져 있음"
    fi
    ;;

  *)
    echo "사용법: bash ./run/redis.sh [start|stop|status]"
    exit 1
    ;;

esac
