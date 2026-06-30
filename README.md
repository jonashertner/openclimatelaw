# OpenClimateLaw

A citation-safe **MCP server** that gives AI assistants grounded access to the world's climate
**litigation** (the Sabin Center's Climate Litigation Database + the Climate Rights Database) and
**legislation** (Climate Change Laws of the World, by Climate Policy Radar) — so they can quote and
cite climate cases and laws **without fabricating** either.

- **Endpoint:** `https://mcp.openclimatelaw.org/mcp` — MCP over Streamable HTTP, no authentication
- **Docs & full connection guide:** <https://openclimatelaw.org>
- 19 tools · 5,027 cases · 81,345 court documents · 5,347 climate laws · open source (MIT)

> **Research preview** — not yet endorsed by the upstream data sources. Please test freely, but don't
> promote it as a public service or cite results in production work.

## Connect in 30 seconds

Point any MCP client at `https://mcp.openclimatelaw.org/mcp` (use the path exactly, no trailing slash).

**Claude Code**
```bash
claude mcp add openclimatelaw https://mcp.openclimatelaw.org/mcp --transport http
```

**ChatGPT** (Plus / Pro / Team / Enterprise)
Settings → **Connectors** → **Add custom connector** → paste `https://mcp.openclimatelaw.org/mcp`.
(Works via the `search` / `fetch` tools ChatGPT's connector calls.)

**Gemini CLI**
```bash
gemini mcp add --transport http openclimatelaw https://mcp.openclimatelaw.org/mcp
```

**Claude Desktop** — add to `claude_desktop_config.json` (via [mcp-remote](https://github.com/geelen/mcp-remote)):
```json
{ "mcpServers": { "openclimatelaw": {
    "command": "npx", "args": ["-y", "mcp-remote", "https://mcp.openclimatelaw.org/mcp"]
} } }
```

**Cursor / Continue / Cline / Zed / VS Code Copilot** and any other MCP client: add the URL above as a
Streamable-HTTP server. Per-client steps (Anthropic API, OpenAI Agents/Responses SDK, Copilot CLI,
Vertex AI): <https://openclimatelaw.org>.

Then ask your assistant:
> *"Find Urgenda v. Netherlands, cite it in en/sabin format, and quote one sentence from its summary
> verbatim — verify the quote first."*

## What it does

19 tools, citation-safe by contract:

- **Discovery** — `search_cases`, `get_case`, `find_cases_by_law`, `get_case_doctrine`
- **Verbatim retrieval & pinpoint** — `get_document_text`, `find_relevant_passage`, `get_passage`
- **Legislation** — `search_statutes`, `get_statute`
- **Citation graph** — `find_citations`, `find_cited_by`, `find_related_cases`
- **Citation safety** — `cite`, `check_claim_support`, `attest_response`, `verify_grounding`
- **Aggregates** — `get_statistics`
- **ChatGPT compatibility** — `search`, `fetch` (the read-only contract ChatGPT connectors require)

## Anti-hallucination contract

The server enforces, in tool design and in its instructions, that an assistant cannot:

- **Fabricate a citation** — `cite(case_id, lang, format)` returns a verbatim `citation_string`; agents
  must call it rather than construct citations from training data.
- **Fabricate a quote** — `check_claim_support(quote, source_id, source_kind)` verifies a quotation
  appears verbatim in a `case_summary`, `document_text`, or `citation_string`.
- **Smuggle either past review** — `attest_response(draft_text, retrieved_ids)` scans a draft for
  citation-shaped strings (US/UK/EU/AU/CA/IE/ZA/IN/CJEU formats) and unverified quotes, and
  `verify_grounding` is an LLM judge for fabricated case names and unsupported holdings.

*Verifiability over veracity: an unverifiable answer cannot be checked; a verifiable one always can.*

## Local development

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d postgres                    # 1. Postgres + pgvector
uv sync                                          # 2. Python deps
uv run yoyo apply --batch \
    --database "postgresql+psycopg://openclimate:dev@localhost:5432/openclimate" \
    migrations                                   # 3. migrations
uv run pytest -q                                 # 4. tests
docker compose up -d --build && curl http://localhost:8000/health   # 5. run server + DB
```

## Data sources & licence

Centred on the [Sabin Center's Climate Litigation Database](https://climatecasechart.com/) (CC-BY 4.0),
with metadata references to the [Climate Rights Database](https://climaterightsdatabase.com/) and a
legislation layer from [Climate Policy Radar](https://climatepolicyradar.org/)'s Climate Change Laws of
the World (CC-BY). Every `citation_string` carries upstream attribution. Server code: MIT.

See `docs/` for the design specs, demo materials, and the data-quality reports shared with the upstream
sources.
