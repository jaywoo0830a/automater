#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
docker compose -f docker/compose.prod.yml up --build -d
echo "prod automator: https://${AUTOMATOR_DOMAIN:-localhost}"
echo "prod ranker:    https://${RANKER_DOMAIN:-localhost}"
