# Production deployment

Single-VPS deployment of OpenClimateLaw on Hetzner Cloud, modelled on the same pattern as `mcp.opencaselaw.ch`.

## Architecture

One Hetzner CX22 (or larger) running Ubuntu 24.04 LTS. Three Docker services orchestrated by `compose.prod.yaml`:

```
Internet ─┐
          ▼
     ┌─ caddy ─┐  (ports 80/443, auto-TLS via Let's Encrypt)
     │         │
     │  reverse_proxy
     │         │
     ▼         ▼
   server   <pages at openclimatelaw.org apex>
     │
     ▼
   postgres  (pgvector/pgvector:pg16, internal-only)
```

- **Caddy** handles TLS termination and reverse-proxies `mcp.openclimatelaw.org` → `server:8000`. The apex `openclimatelaw.org` and `www.openclimatelaw.org` serve a minimal pointer page (replaced by an Astro site in a later plan).
- **server** is the FastMCP application from this repo.
- **postgres** is internal-only — no published port; access via `docker compose exec postgres psql ...` over SSH.

## First-time deployment

### 0. Prerequisites

- Hetzner Cloud project with an SSH key uploaded.
- A fresh CX22 (or larger) running **Ubuntu 24.04 LTS** in a region you choose (Falkenstein recommended for EU latency).
- Domain `openclimatelaw.org` registered (e.g. at GoDaddy).
- The VPS's public IPv4 address.

### 1. DNS — point the domain at the VPS

At your registrar, add three A records on `openclimatelaw.org`:

| Type | Name (host) | Value           | TTL    |
|------|-------------|------------------|--------|
| A    | `@`         | `<VPS_IPv4>`     | 600    |
| A    | `mcp`       | `<VPS_IPv4>`     | 600    |
| A    | `www`       | `<VPS_IPv4>`     | 600    |

GoDaddy specifically: **My Products → DNS → Manage DNS for openclimatelaw.org → Add → Type=A, Name=@/mcp/www, Value=<VPS_IPv4>, TTL=600 seconds**. Save each record. Propagation is usually a few minutes; verify with:

```bash
dig +short mcp.openclimatelaw.org
```

### 2. Bootstrap the VPS

SSH in and run the bootstrap script. This installs Docker + compose, configures `ufw` (22/80/443) and `fail2ban`, clones the repo to `/srv/openclimatelaw`, and seeds `.env.production` with a strong random Postgres password.

```bash
ssh root@<VPS_IPv4>
curl -fsSL https://raw.githubusercontent.com/jonashertner/openclimatelaw/master/deploy/bootstrap.sh -o bootstrap.sh
bash bootstrap.sh
```

Bootstrap finishes printing the next-step commands.

### 3. Apply migrations

```bash
cd /srv/openclimatelaw/deploy
docker compose -f compose.prod.yaml --env-file .env.production --profile migrate run --rm migrate
```

Expected: yoyo applies migrations 0001–0008 in sequence.

### 4. Start the stack

```bash
docker compose -f compose.prod.yaml --env-file .env.production up -d --build
```

Wait ~30-60 seconds for Caddy to obtain TLS certificates.

### 5. Verify

From your laptop:

```bash
curl -s https://mcp.openclimatelaw.org/health
# → {"status":"ok","version":"0.1.0"}
```

And via FastMCP Client:

```bash
uv run python -c '
import asyncio
from fastmcp import Client
async def m():
    async with Client("https://mcp.openclimatelaw.org/mcp") as c:
        tools = await c.list_tools()
        print(sorted(t.name for t in tools))
asyncio.run(m())
'
# → ['attest_response', 'check_claim_support', 'cite', 'get_case', 'get_statistics']
```

### 6. (Optional) Load the Urgenda fixture

To populate the production DB with the demo case while waiting for the live CPR ingestion pipeline:

```bash
ssh root@<VPS_IPv4>
cd /srv/openclimatelaw/deploy
docker compose -f compose.prod.yaml --env-file .env.production exec server \
    uv run python -m ingest.sabin.ingest_one tests/fixtures/sabin_urgenda.json
```

## Subsequent deploys

From your laptop:

```bash
./deploy/deploy.sh root@<VPS_IPv4>
```

This runs `git pull`, applies any pending migrations, and rebuilds + restarts the server container. Postgres and Caddy stay up.

## Operations

### Logs

```bash
ssh root@<VPS_IPv4>
cd /srv/openclimatelaw/deploy
docker compose -f compose.prod.yaml --env-file .env.production logs -f server
docker compose -f compose.prod.yaml --env-file .env.production logs -f caddy
docker compose -f compose.prod.yaml --env-file .env.production logs -f postgres
```

### Backups

Manual snapshot:

```bash
docker compose -f compose.prod.yaml --env-file .env.production exec -T postgres \
    pg_dump -U openclimate openclimate | gzip > /root/backup-$(date +%F).sql.gz
```

Automate later with a `cron` entry + offsite copy (B2/R2/scp). Hetzner snapshots also work for whole-disk backups.

### Updating Caddy / Postgres images

```bash
docker compose -f compose.prod.yaml --env-file .env.production pull
docker compose -f compose.prod.yaml --env-file .env.production up -d
```

### Rotating Postgres password

1. Edit `.env.production`, change `POSTGRES_PASSWORD`.
2. Update inside the running Postgres:
   ```bash
   docker compose -f compose.prod.yaml --env-file .env.production exec postgres \
       psql -U openclimate -c "ALTER USER openclimate PASSWORD 'NEW_VALUE';"
   ```
3. Restart server so it picks up new env: `docker compose ... up -d server`.

## Cost

- Hetzner CX22: €4.51/mo (incl. VAT in EU)
- Domain: ~$10–15/year
- TLS certs: free (Let's Encrypt)
- Total: ~€5/mo

## Out of scope (for now)

- Multi-region / HA — single VPS is fine for v0.1
- Managed Postgres — self-hosted is fine until corpus exceeds a few GB
- CDN — Caddy + HTTP3 is plenty until traffic warrants
- Observability stack — stdout JSON logs ship to journald; add Loki/Grafana when needed
- Astro landing page replacing the apex pointer — Plan 9 work
