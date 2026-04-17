#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
docker compose -f docker/compose.prod.yml up --build -d
echo "prod: https://${DOMAIN:-localhost}  mysql=localhost:3306  observer=active"
