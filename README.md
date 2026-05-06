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

## Ingest a case

Plan 2 ships a fixture-based single-case ingestion. From a running stack:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
  uv run python -m ingest.sabin.ingest_one tests/fixtures/sabin_urgenda.json
```

Then query through the MCP server:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from fastmcp import Client
async def m():
    async with Client("http://localhost:8000/mcp") as c:
        r = await c.call_tool("get_case", {"case_id_or_sabin_id": "urgenda-foundation-v-state-of-the-netherlands"})
        print(r.structured_content["result"]["canonical_title"])
asyncio.run(m())
'
```

## Project status

Plans 1 and 2 complete: schema, MCP server, `get_statistics` and `get_case` tools, fixture-based Sabin ingestion (Urgenda v. Netherlands).
Next: Plan 2.5 — replace fixture with live Climate Policy Radar API client. See `docs/superpowers/plans/`.
