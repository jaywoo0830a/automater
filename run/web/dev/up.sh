#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
set -a; . ./.env; set +a
docker compose -f docker/compose.dev.yml up --build -d
echo "dev: api=http://localhost:${AUTOMATOR_API_PORT:-5000}  web=http://localhost:3000"
