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
    --database "postgresql+psycopg://openclimate:dev@localhost:5432/openclimate" \
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

## Anti-hallucination contract

The MCP enforces the R1, R2, and R5 rules from spec §8 server-side:

- `cite(case_id, lang, format)` — returns the canonical `citation_string` for a case. The R1 contract: never construct citations from training data; always call this tool to get a verbatim citation_string from a previously-retrieved case.
- `check_claim_support(quote, source_id, source_kind)` — verifies a quotation appears verbatim in the named source (`case_summary` | `document_text` | `citation_string`). The R2 contract: never quote what wasn't retrieved.
- `attest_response(draft_text, retrieved_ids)` — scans a draft for citation-shaped strings (ECLI, BVerfGE, BGE, US reporter) and flags any not present in the citation_strings of retrieved cases. Returns `{passed: bool, violations: [...]}`.

R3 (statute text retrieval) and R4 (legislative intent / materialien) are deferred to Plan 6 once CCLW data lands.

## Project status

Plans 1-3 complete: schema, MCP server, five tools (`get_statistics`, `get_case`, `cite`, `check_claim_support`, `attest_response`), fixture-based Sabin ingestion, R1/R2/R5 anti-hallucination contract enforced server-side.
Next: Plan 2.5 — replace fixture with live Climate Policy Radar API client. See `docs/superpowers/plans/`.
