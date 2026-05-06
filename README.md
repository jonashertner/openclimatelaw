# OpenClimateLaw

Public MCP server exposing climate litigation and climate-law data, centred on the Sabin Center's Climate Litigation Database.

See `docs/superpowers/specs/2026-05-05-openclimatelaw-mcp-design.md` for the design.

## Local development

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Start Postgres+pgvector
docker compose up -d postgres

# 2. Install Python deps
uv sync

# 3. Apply migrations
uv run yoyo apply --batch \
    --database "postgresql://openclimate:dev@localhost:5432/openclimate" \
    migrations

# 4. Run tests
uv run pytest -v

# 5. Run the server (foreground)
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
  uv run python -m server.main

# 6. Or run server + DB together
docker compose up -d --build
curl http://localhost:8000/health
```

## Project status

Plan 1 (Foundation) complete: schema + minimal MCP server + `get_statistics` tool.
Next: Plan 2 — Sabin ingestion thin slice. See `docs/superpowers/plans/`.
