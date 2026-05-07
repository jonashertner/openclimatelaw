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

echo "==> Rebuilding and restarting server"
docker compose -f compose.prod.yaml --env-file .env.production up -d --build server

# Wait for server to be healthy before running migrations through it.
sleep 4

echo "==> Applying migrations via the server container (always-fresh image)"
# We bypass the dedicated migrate profile because docker-compose's image
# caching makes it awkward to ensure the migrate image picks up new
# migration files. The server container's image was just rebuilt above
# so we know it has the latest migrations/ directory.
PG_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env.production | cut -d= -f2-)
docker compose -f compose.prod.yaml --env-file .env.production exec -T server \
  uv run yoyo apply --batch \
    --database "postgresql+psycopg://openclimate:${PG_PASSWORD}@postgres:5432/openclimate" \
    /app/migrations

echo "==> Status"
docker compose -f compose.prod.yaml --env-file .env.production ps
EOF

echo
echo "==> Deploy complete. Smoke-test:"
echo "    curl -s https://mcp.openclimatelaw.org/health"
