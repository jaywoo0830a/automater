#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
docker compose -f docker/compose.dev.yml up --build -d
echo "dev: api=http://localhost:5000  web=http://localhost:3000"
