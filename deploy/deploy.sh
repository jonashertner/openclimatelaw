#!/usr/bin/env bash
# Deploy current master to a running OpenClimateLaw VPS.
#
# Usage:   ./deploy/deploy.sh root@<VPS_IP>
#
# Pulls latest master from GitHub on the VPS, rebuilds the server image,
# applies any pending migrations, and restarts services. Caddy and Postgres
# stay up; only the server container is rebuilt.

set -euo pipefail

VPS="${1:?usage: deploy.sh <user@host>}"
APP_DIR="${APP_DIR:-/srv/openclimatelaw}"
BRANCH="${BRANCH:-master}"

ssh "$VPS" bash <<EOF
set -euo pipefail

cd "$APP_DIR"
echo "==> git pull"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

cd "$APP_DIR/deploy"

echo "==> Applying migrations (if any)"
docker compose -f compose.prod.yaml --env-file .env.production --profile migrate run --rm migrate

echo "==> Rebuilding and restarting server"
docker compose -f compose.prod.yaml --env-file .env.production up -d --build server

echo "==> Status"
docker compose -f compose.prod.yaml --env-file .env.production ps
EOF

echo
echo "==> Deploy complete. Smoke-test:"
echo "    curl -s https://mcp.openclimatelaw.org/health"
