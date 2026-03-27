#!/usr/bin/env bash
# run/redis.sh — Redis 세션 저장소
#
#   bash ./run/redis.sh up
#   bash ./run/redis.sh down
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "${1:-up}" in
  up)   docker compose up -d redis && echo "✅ Redis 실행 중 (localhost:6379)" ;;
  down) docker compose down        && echo "✅ 종료 완료" ;;
  *)    echo "사용법: bash ./run/redis.sh [up|down]"; exit 1 ;;
esac
