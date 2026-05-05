# OpenClimateLaw

Public MCP server exposing climate litigation and climate-law data, centred on the Sabin Center's Climate Litigation Database.

See `docs/superpowers/specs/2026-05-05-openclimatelaw-mcp-design.md` for the design.

## Local development

```bash
docker compose up -d postgres
uv sync
uv run yoyo apply --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run python -m server.main
```
