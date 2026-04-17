#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "Stopping services..."
docker compose -f docker/compose.prod.yml down

echo "Removing MySQL volume..."
docker volume rm "$(basename "$(pwd)")_mysql_data" 2>/dev/null \
  || docker volume ls -q | grep mysql_data | xargs -r docker volume rm \
  || echo "  (no volume found — clean start)"

echo "Starting services..."
docker compose -f docker/compose.prod.yml up --build -d

echo "Waiting for MySQL..."
until docker compose -f docker/compose.prod.yml exec mysql mysqladmin ping -h localhost --silent 2>/dev/null; do
  sleep 2
done

echo "Done. MySQL reset complete."
