# OpenClimateLaw MCP — Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a deployable FastMCP server with PostgreSQL+pgvector, the full v0.1 schema migrated, and one working tool (`get_statistics`) that returns valid structured (empty) statistics. End state: `docker compose up` produces a server that responds to MCP tool calls.

**Architecture:** Python 3.14 + uv. FastMCP-based MCP server speaking Streamable-HTTP/SSE at root. Postgres 16 + pgvector via `psycopg[binary,pool]`. Schema managed with `yoyo-migrations`. All v0.1 tables migrated up-front so subsequent plans only add data, not structure. Single tool implemented (`get_statistics`) to prove the server-to-DB-to-MCP-response path end-to-end.

**Tech Stack:** Python 3.14, uv, FastMCP, psycopg 3, yoyo-migrations, pgvector, pytest, docker-compose, ruff (lint+format), pyright (typecheck).

---

## Files

**Create:**
- `pyproject.toml` — project metadata, dependencies, ruff/pyright config
- `.python-version` — `3.14`
- `.gitignore`
- `README.md` — minimal project overview
- `compose.yaml` — docker-compose for local Postgres+pgvector
- `Dockerfile` — server container
- `server/__init__.py`
- `server/main.py` — FastMCP app entrypoint
- `server/db.py` — Postgres connection pool helper
- `server/settings.py` — env-driven config (Pydantic Settings)
- `server/tools/__init__.py`
- `server/tools/statistics.py` — `get_statistics` implementation
- `migrations/` — yoyo migrations directory
- `migrations/0001-create-vocabulary-tables.sql`
- `migrations/0002-create-case-tables.sql`
- `migrations/0003-create-document-tables.sql`
- `migrations/0004-create-statute-tables.sql`
- `migrations/0005-create-citation-tables.sql`
- `migrations/0006-create-merge-candidate-table.sql`
- `migrations/0007-enable-pgvector-and-indexes.sql`
- `tests/__init__.py`
- `tests/conftest.py` — pytest fixtures (Postgres test DB)
- `tests/test_health.py` — server health check
- `tests/test_statistics.py` — `get_statistics` tool tests
- `tests/test_migrations.py` — migration smoke test
- `.github/workflows/ci.yaml` — CI: lint + typecheck + test

---

## Task 1: Project skeleton with `uv` and `pyproject.toml`

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Initialize uv project**

Run:

```bash
cd /Users/jonashertner/Projects/openclimatelaw
uv init --bare --python 3.14
```

Expected: creates `.python-version` and a minimal `pyproject.toml`.

- [ ] **Step 2: Replace `pyproject.toml` with the full version**

Write `pyproject.toml`:

```toml
[project]
name = "openclimatelaw"
version = "0.1.0"
description = "Public MCP server exposing the world's climate litigation and climate-law corpus"
readme = "README.md"
requires-python = ">=3.14"
license = { text = "MIT" }
authors = [{ name = "Jonas Hertner", email = "jonashertner@protonmail.ch" }]

dependencies = [
    "fastmcp>=3.0.2",
    "psycopg[binary,pool]>=3.2.0",
    "pgvector>=0.3.0",
    "pydantic-settings>=2.5.0",
    "yoyo-migrations>=9.0.0",
    "structlog>=24.4.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.7.0",
    "pyright>=1.1.380",
    "httpx>=0.27.0",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
include = ["server", "tests"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.pyright/
.venv/
.env
.env.local
*.egg-info/
dist/
build/
htmlcov/
.coverage
node_modules/
```

- [ ] **Step 4: Write minimal `README.md`**

```markdown
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
```

- [ ] **Step 5: Lock dependencies**

Run: `uv sync`
Expected: creates `uv.lock`, installs dependencies into `.venv`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version .gitignore README.md uv.lock
git commit -m "chore: scaffold project with uv, FastMCP, psycopg"
```

---

## Task 2: docker-compose with Postgres+pgvector

**Files:**
- Create: `compose.yaml`

- [ ] **Step 1: Write `compose.yaml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: openclimate
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: openclimate
    ports:
      - "5432:5432"
    volumes:
      - openclimate-pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openclimate -d openclimate"]
      interval: 2s
      timeout: 2s
      retries: 20

volumes:
  openclimate-pg:
```

- [ ] **Step 2: Start Postgres and verify**

Run:

```bash
docker compose up -d postgres
docker compose ps postgres
```

Expected: `postgres` container is `running` and `healthy`.

- [ ] **Step 3: Verify pgvector extension is available**

Run:

```bash
docker compose exec postgres psql -U openclimate -d openclimate -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Expected: returns one row with `vector | <version>`.

- [ ] **Step 4: Commit**

```bash
git add compose.yaml
git commit -m "chore: add docker-compose with pgvector/pg16"
```

---

## Task 3: Settings module (Pydantic Settings)

**Files:**
- Create: `server/__init__.py`
- Create: `server/settings.py`
- Create: `tests/__init__.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test `tests/test_settings.py`**

```python
import os

from server.settings import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    settings = Settings()
    assert settings.database_url == "postgresql://u:p@localhost:5432/db"
    assert settings.log_level == "INFO"


def test_settings_defaults_when_optional_unset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = Settings()
    assert settings.log_level == "INFO"


def test_settings_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.settings'` (or similar).

- [ ] **Step 3: Write `server/__init__.py` and `tests/__init__.py`**

`server/__init__.py`:

```python
```

`tests/__init__.py`:

```python
```

- [ ] **Step 4: Implement `server/settings.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"
    server_host: str = "0.0.0.0"
    server_port: int = 8000


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_settings.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/__init__.py server/settings.py tests/__init__.py tests/test_settings.py
git commit -m "feat: add env-driven Settings via pydantic-settings"
```

---

## Task 4: Postgres connection pool

**Files:**
- Create: `server/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test `tests/test_db.py`**

```python
import pytest

from server.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_pool_executes_select_one():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 AS n")
            row = await cur.fetchone()
            assert row == (1,)
    await close_pool()
```

- [ ] **Step 2: Write `tests/conftest.py` to set DATABASE_URL for the test DB**

```python
import os

import pytest


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get(
            "DATABASE_URL", "postgresql://openclimate:dev@localhost:5432/openclimate"
        ),
    )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.db'`.

- [ ] **Step 4: Implement `server/db.py`**

```python
from psycopg_pool import AsyncConnectionPool

from server.settings import get_settings

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            open=False,
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
```

- [ ] **Step 5: Run test to verify it passes (Postgres must be running)**

Run:

```bash
docker compose up -d postgres
uv run pytest tests/test_db.py -v
```

Expected: 1 PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/db.py tests/conftest.py tests/test_db.py
git commit -m "feat: add async psycopg connection pool"
```

---

## Task 5: Migrations infrastructure with yoyo

**Files:**
- Create: `migrations/0001-create-vocabulary-tables.sql`
- Create: `tests/test_migrations.py`

- [ ] **Step 1: Write the failing test `tests/test_migrations.py`**

```python
import pytest

from server.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_vocabulary_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('vocabulary_jurisdiction', 'vocabulary_court',
                                     'vocabulary_claim_type', 'vocabulary_status',
                                     'vocabulary_outcome', 'vocabulary_document_category')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == [
                "vocabulary_claim_type",
                "vocabulary_court",
                "vocabulary_document_category",
                "vocabulary_jurisdiction",
                "vocabulary_outcome",
                "vocabulary_status",
            ]
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: FAIL — assertion error showing `[]` (no vocabulary tables yet).

- [ ] **Step 3: Write `migrations/0001-create-vocabulary-tables.sql`**

```sql
-- Vocabulary tables: controlled values mirrored from upstream sources (Sabin, CCLW, etc).
-- Each vocabulary record carries a source_version so we can detect upstream taxonomy changes.

CREATE TABLE vocabulary_jurisdiction (
    code TEXT PRIMARY KEY,                       -- ISO 3166-1 alpha-2, or special codes (ICJ, IACTHR, ECTHR, etc.)
    name TEXT NOT NULL,
    kind TEXT NOT NULL,                          -- 'national' | 'sub_national' | 'international' | 'regional'
    source TEXT NOT NULL,                        -- 'sabin' | 'cclw' | 'manual'
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_court (
    id TEXT PRIMARY KEY,                         -- Sabin's court id
    name TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    level TEXT,                                  -- 'supreme' | 'appellate' | 'trial' | 'tribunal' | 'other'
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_claim_type (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_status (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_outcome (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_document_category (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 4: Apply migration**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
```

Expected: applies migration 0001; output ends with "applied 1 migration".

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: 1 PASSED.

- [ ] **Step 6: Commit**

```bash
git add migrations/0001-create-vocabulary-tables.sql tests/test_migrations.py
git commit -m "feat: migration 0001 — vocabulary tables"
```

---

## Task 6: Migration 0002 — case tables

**Files:**
- Create: `migrations/0002-create-case-tables.sql`
- Modify: `tests/test_migrations.py` (add a case-table check)

- [ ] **Step 1: Add a failing test for case tables to `tests/test_migrations.py`**

Append:

```python
@pytest.mark.asyncio
async def test_case_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('case_record', 'case_party', 'case_claim_type',
                                     'citation_string')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == [
                "case_claim_type",
                "case_party",
                "case_record",
                "citation_string",
            ]
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_case_tables_exist -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0002-create-case-tables.sql`**

```sql
-- Case tables. `case_record` is the canonical case (named `case_record` because
-- `case` is a Postgres reserved word). Sabin's case_id is the natural key when present.

CREATE TABLE case_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sabin_id TEXT UNIQUE,
    canonical_title TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    court_id TEXT REFERENCES vocabulary_court(id),
    filing_date DATE,
    decision_date DATE,
    status_code TEXT REFERENCES vocabulary_status(code),
    outcome_code TEXT REFERENCES vocabulary_outcome(code),
    summary TEXT,
    summary_lang TEXT NOT NULL DEFAULT 'en',
    primary_source TEXT NOT NULL CHECK (
        primary_source IN ('sabin', 'climate_rights', 'c2li', 'melbourne', 'redline')
    ),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX case_record_jurisdiction_idx ON case_record(jurisdiction_code);
CREATE INDEX case_record_court_idx ON case_record(court_id);
CREATE INDEX case_record_filing_date_idx ON case_record(filing_date);
CREATE INDEX case_record_summary_fts_idx ON case_record
    USING GIN (to_tsvector('simple', coalesce(summary, '')));

CREATE TABLE case_party (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('plaintiff', 'defendant', 'intervenor', 'amicus')),
    name TEXT NOT NULL,
    party_type TEXT,                              -- 'individual' | 'ngo' | 'corporation' | 'state' | 'sub_state'
    ord INT NOT NULL,                             -- preserves source ordering
    PRIMARY KEY (case_id, side, ord)
);

CREATE INDEX case_party_name_idx ON case_party USING GIN (to_tsvector('simple', name));

CREATE TABLE case_claim_type (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    claim_type_code TEXT NOT NULL REFERENCES vocabulary_claim_type(code),
    PRIMARY KEY (case_id, claim_type_code)
);

CREATE TABLE citation_string (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    lang TEXT NOT NULL,
    format TEXT NOT NULL,                          -- 'sabin' | 'bluebook' | 'oscola' | 'iclq' | source-native
    text TEXT NOT NULL,
    PRIMARY KEY (case_id, lang, format)
);

CREATE INDEX citation_string_text_idx ON citation_string(text);
```

- [ ] **Step 4: Apply migration**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
```

Expected: applies migration 0002.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_migrations.py -v`
Expected: 2 PASSED.

- [ ] **Step 6: Commit**

```bash
git add migrations/0002-create-case-tables.sql tests/test_migrations.py
git commit -m "feat: migration 0002 — case_record, case_party, case_claim_type, citation_string"
```

---

## Task 7: Migration 0003 — document tables

**Files:**
- Create: `migrations/0003-create-document-tables.sql`
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Add a failing test for document tables**

Append to `tests/test_migrations.py`:

```python
@pytest.mark.asyncio
async def test_document_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'document'
                ORDER BY column_name
                """
            )
            rows = await cur.fetchall()
            names = {r[0] for r in rows}
            for required in [
                "id", "case_id", "category_code", "title",
                "filed_date", "filed_by", "upstream_url", "storage_url",
                "text", "text_lang", "text_extraction_method",
                "text_translation_en", "provenance", "created_at",
            ]:
                assert required in names, f"missing column: {required}"
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_document_table_exists -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0003-create-document-tables.sql`**

```sql
-- Document table. `embedding` column is added in migration 0007 once pgvector is enabled,
-- to keep this migration runnable on a stock Postgres image during dev/test.

CREATE TABLE document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    category_code TEXT NOT NULL REFERENCES vocabulary_document_category(code),
    title TEXT NOT NULL,
    filed_date DATE,
    filed_by TEXT,
    upstream_url TEXT NOT NULL,
    storage_url TEXT,                              -- R2 URL of mirrored PDF, NULL until ingested
    text TEXT,                                      -- extracted full text
    text_lang TEXT,
    text_extraction_method TEXT
        CHECK (text_extraction_method IS NULL OR
               text_extraction_method IN ('pymupdf', 'tesseract', 'upstream_provided')),
    text_translation_en TEXT,                       -- MT to English when text_lang != 'en'
    text_content_hash TEXT,                         -- sha256 of text; cache key for translation/embeddings
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX document_case_idx ON document(case_id);
CREATE INDEX document_category_idx ON document(category_code);
CREATE INDEX document_text_fts_idx ON document
    USING GIN (to_tsvector('simple', coalesce(text, '')));
CREATE INDEX document_translation_fts_idx ON document
    USING GIN (to_tsvector('english', coalesce(text_translation_en, '')));
```

- [ ] **Step 4: Apply migration and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_migrations.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add migrations/0003-create-document-tables.sql tests/test_migrations.py
git commit -m "feat: migration 0003 — document table"
```

---

## Task 8: Migration 0004 — statute and case_statute tables

**Files:**
- Create: `migrations/0004-create-statute-tables.sql`
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_migrations.py`:

```python
@pytest.mark.asyncio
async def test_statute_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('statute', 'case_statute')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == ["case_statute", "statute"]
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_statute_tables_exist -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0004-create-statute-tables.sql`**

```sql
CREATE TABLE statute (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cclw_id TEXT UNIQUE,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    short_title TEXT NOT NULL,
    long_title TEXT,
    enacted_date DATE,
    status TEXT NOT NULL,                            -- CCLW status enum, sourced verbatim
    text TEXT,
    text_lang TEXT,
    text_content_hash TEXT,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX statute_jurisdiction_idx ON statute(jurisdiction_code);
CREATE INDEX statute_text_fts_idx ON statute
    USING GIN (to_tsvector('simple', coalesce(text, '')));
CREATE INDEX statute_short_title_fts_idx ON statute
    USING GIN (to_tsvector('simple', short_title));

CREATE TABLE case_statute (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    statute_id UUID NOT NULL REFERENCES statute(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL CHECK (
        relationship IN ('enforces', 'challenges', 'interprets', 'cited', 'referenced')
    ),
    source_of_link TEXT NOT NULL,
    PRIMARY KEY (case_id, statute_id, relationship)
);
```

- [ ] **Step 4: Apply and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_migrations.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add migrations/0004-create-statute-tables.sql tests/test_migrations.py
git commit -m "feat: migration 0004 — statute and case_statute"
```

---

## Task 9: Migration 0005 — citation edge graph

**Files:**
- Create: `migrations/0005-create-citation-tables.sql`
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_migrations.py`:

```python
@pytest.mark.asyncio
async def test_citation_edge_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'citation_edge'
                """
            )
            row = await cur.fetchone()
            assert row is not None
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_citation_edge_table_exists -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0005-create-citation-tables.sql`**

```sql
-- Citation graph. `cited_case_id` is non-null when target is in our DB;
-- `cited_authority` is non-null when the cited target is external (foreign court,
-- treaty, statute, etc.). Both can be null only if neither was extracted (rare).

CREATE TABLE citation_edge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    citing_document_id UUID REFERENCES document(id) ON DELETE SET NULL,
    cited_case_id UUID REFERENCES case_record(id) ON DELETE SET NULL,
    cited_authority TEXT,
    citation_string TEXT NOT NULL,
    span_in_document JSONB,                          -- {char_start, char_end}
    source_of_edge TEXT NOT NULL CHECK (
        source_of_edge IN ('cpr', 'sabin_structured', 'inferred_nlp', 'manual')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX citation_edge_citing_idx ON citation_edge(citing_case_id);
CREATE INDEX citation_edge_cited_idx ON citation_edge(cited_case_id);
```

- [ ] **Step 4: Apply and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_migrations.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add migrations/0005-create-citation-tables.sql tests/test_migrations.py
git commit -m "feat: migration 0005 — citation_edge graph table"
```

---

## Task 10: Migration 0006 — merge_candidate dedup queue

**Files:**
- Create: `migrations/0006-create-merge-candidate-table.sql`
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_migrations.py`:

```python
@pytest.mark.asyncio
async def test_merge_candidate_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'merge_candidate'
                """
            )
            row = await cur.fetchone()
            assert row is not None
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_merge_candidate_table_exists -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0006-create-merge-candidate-table.sql`**

```sql
CREATE TABLE merge_candidate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id_a UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    case_id_b UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    score FLOAT NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    features JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'merged', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CONSTRAINT merge_candidate_distinct CHECK (case_id_a <> case_id_b)
);

CREATE INDEX merge_candidate_status_idx ON merge_candidate(status);
CREATE INDEX merge_candidate_pair_idx ON merge_candidate(case_id_a, case_id_b);
```

- [ ] **Step 4: Apply and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_migrations.py -v
```

Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add migrations/0006-create-merge-candidate-table.sql tests/test_migrations.py
git commit -m "feat: migration 0006 — merge_candidate dedup queue"
```

---

## Task 11: Migration 0007 — pgvector embeddings

**Files:**
- Create: `migrations/0007-enable-pgvector-and-indexes.sql`
- Modify: `tests/test_migrations.py`

- [ ] **Step 1: Add a failing test for embedding columns**

Append to `tests/test_migrations.py`:

```python
@pytest.mark.asyncio
async def test_embedding_columns_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name, column_name, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'embedding'
                  AND table_name IN ('document', 'statute')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [(r[0], r[1], r[2]) for r in rows]
            assert ("document", "embedding", "vector") in names
            assert ("statute", "embedding", "vector") in names
    await close_pool()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migrations.py::test_embedding_columns_exist -v`
Expected: FAIL.

- [ ] **Step 3: Write `migrations/0007-enable-pgvector-and-indexes.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document ADD COLUMN embedding vector(1024);
ALTER TABLE statute  ADD COLUMN embedding vector(1024);

-- HNSW indexes for cosine similarity. m=16, ef_construction=64 are pgvector defaults
-- and a reasonable starting point for the v0.1 scale (~15k document embeddings).
CREATE INDEX document_embedding_hnsw_idx ON document
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX statute_embedding_hnsw_idx ON statute
    USING hnsw (embedding vector_cosine_ops);
```

- [ ] **Step 4: Apply and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_migrations.py -v
```

Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add migrations/0007-enable-pgvector-and-indexes.sql tests/test_migrations.py
git commit -m "feat: migration 0007 — enable pgvector, add embedding columns + HNSW indexes"
```

---

## Task 12: FastMCP server scaffold with `/health`

**Files:**
- Create: `server/main.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write the failing test `tests/test_health.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from server.main import build_app


@pytest.mark.asyncio
async def test_health_returns_ok():
    app = build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.main'`.

- [ ] **Step 3: Write `server/main.py`**

```python
from importlib.metadata import version

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


def build_mcp() -> FastMCP:
    mcp = FastMCP(name="openclimatelaw")
    return mcp


def build_app() -> Starlette:
    mcp = build_mcp()
    mcp_app = mcp.streamable_http_app()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": version("openclimatelaw"),
            }
        )

    return Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ]
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    from server.settings import get_settings

    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_health.py -v`
Expected: 1 PASSED.

- [ ] **Step 5: Add uvicorn to dependencies**

Edit `pyproject.toml`, add to `[project].dependencies`:

```toml
    "uvicorn[standard]>=0.32.0",
```

Run: `uv sync`

- [ ] **Step 6: Smoke test the running server**

Run in one terminal:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate uv run python -m server.main
```

In another terminal:

```bash
curl -s http://localhost:8000/health | jq
```

Expected: `{"status": "ok", "version": "0.1.0"}`

Stop the server with Ctrl-C.

- [ ] **Step 7: Commit**

```bash
git add server/main.py tests/test_health.py pyproject.toml uv.lock
git commit -m "feat: FastMCP server scaffold with /health endpoint"
```

---

## Task 13: First MCP tool — `get_statistics`

**Files:**
- Create: `server/tools/__init__.py`
- Create: `server/tools/statistics.py`
- Create: `tests/test_statistics.py`
- Modify: `server/main.py` (register tool)

- [ ] **Step 1: Write the failing test `tests/test_statistics.py`**

```python
import pytest

from server.tools.statistics import get_statistics


@pytest.mark.asyncio
async def test_statistics_empty_database_returns_zeros():
    result = await get_statistics(scope="all", group_by=None)
    assert result["scope"] == "all"
    assert result["totals"]["case_count"] == 0
    assert result["totals"]["document_count"] == 0
    assert result["totals"]["statute_count"] == 0
    assert result["totals"]["jurisdiction_count"] == 0
    assert result["last_refresh_at"] is None


@pytest.mark.asyncio
async def test_statistics_group_by_jurisdiction_returns_empty_list_when_no_data():
    result = await get_statistics(scope="all", group_by="jurisdiction")
    assert result["groups"] == []


@pytest.mark.asyncio
async def test_statistics_invalid_scope_raises():
    with pytest.raises(ValueError, match="invalid scope"):
        await get_statistics(scope="bogus", group_by=None)


@pytest.mark.asyncio
async def test_statistics_invalid_group_by_raises():
    with pytest.raises(ValueError, match="invalid group_by"):
        await get_statistics(scope="all", group_by="bogus")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_statistics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server.tools.statistics'`.

- [ ] **Step 3: Write `server/tools/__init__.py` (empty)**

```python
```

- [ ] **Step 4: Write `server/tools/statistics.py`**

```python
from typing import Any, Literal

from server.db import get_pool

Scope = Literal["all", "sabin", "cclw"]
GroupBy = Literal["jurisdiction", "claim_type", "year", "status", "outcome"]

VALID_SCOPES = {"all", "sabin", "cclw"}
VALID_GROUP_BY = {"jurisdiction", "claim_type", "year", "status", "outcome"}


async def get_statistics(
    scope: str = "all",
    group_by: str | None = None,
) -> dict[str, Any]:
    """Return structured statistics over the corpus.

    Args:
        scope: 'all' | 'sabin' | 'cclw'.
        group_by: when provided, returns per-group counts in addition to totals.

    Returns:
        A dict with `scope`, `totals`, optional `groups`, and `last_refresh_at`.
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"invalid scope: {scope!r} (must be one of {sorted(VALID_SCOPES)})")
    if group_by is not None and group_by not in VALID_GROUP_BY:
        raise ValueError(
            f"invalid group_by: {group_by!r} (must be one of {sorted(VALID_GROUP_BY)})"
        )

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            scope_filter = ""
            if scope == "sabin":
                scope_filter = "WHERE primary_source = 'sabin'"
            elif scope == "cclw":
                # CCLW lives in `statute`; cases not affected.
                scope_filter = "WHERE 1=0"  # no cases for cclw scope

            await cur.execute(f"SELECT count(*) FROM case_record {scope_filter}")
            (case_count,) = await cur.fetchone()  # type: ignore[misc]

            await cur.execute(
                f"""
                SELECT count(*) FROM document d
                {("JOIN case_record c ON c.id = d.case_id " + scope_filter) if scope_filter else ""}
                """
            )
            (document_count,) = await cur.fetchone()  # type: ignore[misc]

            statute_count = 0
            if scope in ("all", "cclw"):
                await cur.execute("SELECT count(*) FROM statute")
                (statute_count,) = await cur.fetchone()  # type: ignore[misc]

            await cur.execute(
                f"""
                SELECT count(DISTINCT jurisdiction_code) FROM case_record {scope_filter}
                """
            )
            (jurisdiction_count,) = await cur.fetchone()  # type: ignore[misc]

            groups: list[dict[str, Any]] = []
            if group_by is not None:
                groups = await _compute_groups(cur, scope, group_by)

            await cur.execute(
                "SELECT max(updated_at) FROM case_record"
            )
            (last_refresh_at,) = await cur.fetchone()  # type: ignore[misc]

    result: dict[str, Any] = {
        "scope": scope,
        "totals": {
            "case_count": case_count,
            "document_count": document_count,
            "statute_count": statute_count,
            "jurisdiction_count": jurisdiction_count,
        },
        "last_refresh_at": last_refresh_at.isoformat() if last_refresh_at is not None else None,
    }
    if group_by is not None:
        result["groups"] = groups
        result["group_by"] = group_by

    return result


async def _compute_groups(cur: Any, scope: str, group_by: str) -> list[dict[str, Any]]:
    scope_filter = ""
    if scope == "sabin":
        scope_filter = "WHERE primary_source = 'sabin'"
    elif scope == "cclw":
        return []

    if group_by == "jurisdiction":
        await cur.execute(
            f"""
            SELECT jurisdiction_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY jurisdiction_code
            ORDER BY n DESC, jurisdiction_code
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "claim_type":
        await cur.execute(
            f"""
            SELECT cct.claim_type_code, count(*) as n
            FROM case_claim_type cct
            JOIN case_record c ON c.id = cct.case_id
            {scope_filter}
            GROUP BY cct.claim_type_code
            ORDER BY n DESC, cct.claim_type_code
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "year":
        await cur.execute(
            f"""
            SELECT extract(year from filing_date)::int AS y, count(*) AS n
            FROM case_record
            {scope_filter}
            {"AND" if scope_filter else "WHERE"} filing_date IS NOT NULL
            GROUP BY y
            ORDER BY y
            """
        )
        return [{"key": str(r[0]), "count": r[1]} for r in await cur.fetchall()]
    if group_by == "status":
        await cur.execute(
            f"""
            SELECT status_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY status_code
            ORDER BY n DESC NULLS LAST
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "outcome":
        await cur.execute(
            f"""
            SELECT outcome_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY outcome_code
            ORDER BY n DESC NULLS LAST
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]

    return []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_statistics.py -v`
Expected: 4 PASSED.

- [ ] **Step 6: Register the tool with FastMCP in `server/main.py`**

Modify `build_mcp()` in `server/main.py`:

```python
def build_mcp() -> FastMCP:
    mcp = FastMCP(name="openclimatelaw")

    from server.tools.statistics import get_statistics as _get_statistics

    @mcp.tool(
        name="get_statistics",
        description=(
            "Return structured statistics over the climate-litigation corpus. "
            "scope: 'all' | 'sabin' | 'cclw'. "
            "group_by: 'jurisdiction' | 'claim_type' | 'year' | 'status' | 'outcome' | null. "
            "Returns case_count, document_count, statute_count, jurisdiction_count, "
            "and per-group counts when group_by is set."
        ),
    )
    async def get_statistics_tool(
        scope: str = "all",
        group_by: str | None = None,
    ) -> dict[str, object]:
        return await _get_statistics(scope=scope, group_by=group_by)

    return mcp
```

- [ ] **Step 7: Add an integration test that calls the tool via FastMCP Client (handles the protocol handshake)**

Append to `tests/test_statistics.py`:

```python
import pytest
from fastmcp import Client

from server.main import build_mcp


@pytest.mark.asyncio
async def test_get_statistics_via_fastmcp_client():
    mcp = build_mcp()
    async with Client(mcp) as client:
        # tools/list should include get_statistics
        tools = await client.list_tools()
        assert any(t.name == "get_statistics" for t in tools)

        # tools/call should return a structured payload with totals
        result = await client.call_tool("get_statistics", {"scope": "all"})
        # FastMCP's CallToolResult exposes structured_content for tools returning dicts
        assert result.structured_content is not None
        assert result.structured_content["totals"]["case_count"] == 0
        assert result.structured_content["scope"] == "all"
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS (settings: 3, db: 1, migrations: 7, health: 1, statistics: 5 = 17 PASSED).

- [ ] **Step 9: Commit**

```bash
git add server/tools/__init__.py server/tools/statistics.py server/main.py tests/test_statistics.py
git commit -m "feat: get_statistics tool — first MCP-exposed read query"
```

---

## Task 14: Dockerfile for the server

**Files:**
- Create: `Dockerfile`
- Modify: `compose.yaml` (add `server` service)

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --frozen --no-dev

COPY server /app/server
COPY migrations /app/migrations

EXPOSE 8000
CMD ["uv", "run", "--no-dev", "python", "-m", "server.main"]
```

- [ ] **Step 2: Append `server` service to `compose.yaml`**

Replace `compose.yaml` with:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: openclimate
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: openclimate
    ports:
      - "5432:5432"
    volumes:
      - openclimate-pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openclimate -d openclimate"]
      interval: 2s
      timeout: 2s
      retries: 20

  server:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://openclimate:dev@postgres:5432/openclimate
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"

volumes:
  openclimate-pg:
```

- [ ] **Step 3: Build and run**

Run:

```bash
docker compose build server
docker compose up -d
docker compose ps
```

Expected: `postgres` healthy, `server` running.

- [ ] **Step 4: Apply migrations against the dockerized DB and smoke-test the server**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
curl -s http://localhost:8000/health | jq
```

Expected: health returns `{"status": "ok", "version": "0.1.0"}`.

- [ ] **Step 5: Smoke-test the deployed server via FastMCP Client**

The MCP Streamable-HTTP protocol requires an initialize handshake before tool calls — `curl` alone is awkward. Use the fastmcp Client instead:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools])
        result = await client.call_tool("get_statistics", {"scope": "all"})
        print("stats:", result.structured_content)

asyncio.run(main())
'
```

Expected output:

```
tools: ['get_statistics']
stats: {'scope': 'all', 'totals': {'case_count': 0, 'document_count': 0, 'statute_count': 0, 'jurisdiction_count': 0}, 'last_refresh_at': None}
```

- [ ] **Step 6: Stop and commit**

```bash
docker compose down
git add Dockerfile compose.yaml
git commit -m "chore: Dockerfile and docker-compose server service"
```

---

## Task 15: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yaml`

- [ ] **Step 1: Write `.github/workflows/ci.yaml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: openclimate
          POSTGRES_PASSWORD: dev
          POSTGRES_DB: openclimate
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U openclimate -d openclimate"
          --health-interval 2s
          --health-timeout 2s
          --health-retries 20
    env:
      DATABASE_URL: postgresql://openclimate:dev@localhost:5432/openclimate
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.4"

      - name: Set Python version
        run: uv python install 3.14

      - name: Sync dependencies
        run: uv sync --frozen

      - name: Lint
        run: uv run ruff check .

      - name: Format check
        run: uv run ruff format --check .

      - name: Typecheck
        run: uv run pyright

      - name: Apply migrations
        run: uv run yoyo apply --batch --database "$DATABASE_URL" migrations

      - name: Run tests
        run: uv run pytest -v
```

- [ ] **Step 2: Verify locally that lint and typecheck pass**

Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Fix any reported issues before commit.

Expected (after fixes): all three commands exit 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yaml
git commit -m "ci: GitHub Actions — lint, typecheck, migrations, tests"
```

---

## Task 16: Final smoke test and Plan 1 wrap

**Files:**
- Modify: `README.md` (document local dev workflow)

- [ ] **Step 1: Run the full local workflow from a clean state**

```bash
docker compose down -v
docker compose up -d postgres
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest -v
docker compose up -d --build server
sleep 3
curl -s http://localhost:8000/health
echo
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "get_statistics" in names, names
        print("tools:", names)
        result = await client.call_tool("get_statistics", {"scope": "all"})
        print("stats:", result.structured_content)

asyncio.run(main())
'
```

Expected:
- All tests PASS
- `/health` returns `{"status":"ok","version":"0.1.0"}`
- The Python smoke-test prints `tools: ['get_statistics']` and an empty-totals stats payload.

- [ ] **Step 2: Update `README.md` with the verified local workflow**

Replace the local-development section with:

```markdown
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
```

- [ ] **Step 3: Tear down**

Run: `docker compose down`

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: document verified local dev workflow"
```

---

## Verification checklist (post-Plan-1)

- [ ] All 7 migrations applied; all 7 migration tests pass.
- [ ] `get_statistics` returns valid structure on empty DB.
- [ ] `/health` returns `{"status": "ok", "version": "0.1.0"}`.
- [ ] MCP `tools/list` lists `get_statistics`.
- [ ] CI passes on push (lint, format, typecheck, migrations, tests).
- [ ] `docker compose up -d` produces a healthy stack.

When all boxes are checked, Plan 1 is complete and Plan 2 (Sabin ingestion thin slice) becomes the next deliverable.
