# OpenClimateLaw MCP — Plan 2: Sabin Ingestion Thin Slice

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End-to-end ingestion of one real Sabin case (Urgenda v. Netherlands) from a JSON fixture into Postgres, retrievable via a `get_case(case_id)` MCP tool with field-level provenance. Establishes the ingestion pipeline patterns (vocabulary seeding, Pydantic models, UPSERT, provenance) without yet depending on Climate Policy Radar's undocumented frontend API.

**Architecture:** New `ingest/` package alongside `server/`. Sabin records flow: JSON fixture → Pydantic model (`SabinCaseRecord`) → canonical schema dicts (`parse.py`) → idempotent UPSERT (`upsert.py`) → Postgres. Vocabulary tables are seeded by a new migration (0008) with the minimum values needed by the Urgenda case plus a small surrounding margin. The MCP exposes `get_case(case_id)` reading the persisted record back with all child entities (parties, claim types, citation strings) and a `provenance` map.

**Tech Stack:** Same as Plan 1 (Python 3.14, uv, FastMCP, psycopg, yoyo, pytest) plus `pydantic>=2.9.0` (Pydantic v2 is already a transitive dep via pydantic-settings; declare it explicitly). `structlog` (already a dep, finally wired here).

**Why fixture-based:** CPR's organisation-facing API is not yet GA (per spec §6.1); their frontend-serving API is undocumented and discovering it is a one-off scrape exercise. We separate that concern: Plan 2 nails ingestion plumbing against a hand-authored fixture (real Sabin data, transcribed from `climatecasechart.com`), Plan 2.5 swaps the fixture source for a live HTTP client. This keeps the plumbing testable, reproducible in CI, and decoupled from upstream availability.

---

## Files

**Create:**
- `ingest/__init__.py`
- `ingest/_provenance.py` — Field-level provenance JSONB helpers
- `ingest/sabin/__init__.py`
- `ingest/sabin/models.py` — Pydantic models matching Sabin's record shape
- `ingest/sabin/parse.py` — Sabin model → canonical schema dicts
- `ingest/sabin/upsert.py` — Idempotent UPSERT against Postgres
- `ingest/sabin/ingest_one.py` — CLI entry point: `python -m ingest.sabin.ingest_one <path>`
- `migrations/0008-seed-minimal-vocabularies.sql` — Minimal vocab values for the demo
- `server/_logging.py` — structlog configuration
- `server/tools/cases.py` — `get_case(case_id)` tool implementation
- `tests/fixtures/sabin_urgenda.json` — Real Urgenda data, hand-authored
- `tests/test_logging.py` — structlog wiring smoke test
- `tests/test_ingest_provenance.py`
- `tests/test_ingest_sabin_models.py`
- `tests/test_ingest_sabin_parse.py`
- `tests/test_ingest_sabin_upsert.py`
- `tests/test_get_case_tool.py`
- `tests/test_e2e_ingest_and_query.py` — End-to-end ingest + MCP query

**Modify:**
- `server/main.py` — Register `get_case` tool and wire structlog at startup
- `pyproject.toml` — Add explicit `pydantic` dep
- `README.md` — Add ingestion section

---

## Task 1: `ingest/` package skeleton + structlog dep declaration

**Files:**
- Create: `ingest/__init__.py`
- Create: `ingest/sabin/__init__.py`
- Modify: `pyproject.toml` (add `pydantic>=2.9.0` to deps)

- [ ] **Step 1: Create empty package init files**

```bash
mkdir -p ingest/sabin
```

`ingest/__init__.py`:

```python
```

`ingest/sabin/__init__.py`:

```python
```

- [ ] **Step 2: Add explicit pydantic dep to `pyproject.toml`**

Insert into `[project].dependencies`, alphabetically ordered:

```toml
    "pydantic>=2.9.0",
```

- [ ] **Step 3: Update `pyright` include in `pyproject.toml`**

Modify the `[tool.pyright]` block:

```toml
[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
include = ["server", "ingest", "tests"]
```

- [ ] **Step 4: Sync and verify**

Run:

```bash
uv sync
uv run ruff check .
uv run pyright
uv run pytest -v
```

Expected: lock updates, all 17 tests still pass, no new lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add ingest/ pyproject.toml uv.lock
git commit -m "chore: add ingest/ package skeleton + explicit pydantic dep"
```

---

## Task 2: Wire structlog as the server-wide logger

**Files:**
- Create: `server/_logging.py`
- Create: `tests/test_logging.py`
- Modify: `server/main.py` (call `configure_logging()` at app startup)

- [ ] **Step 1: Write the failing test `tests/test_logging.py`**

```python
import json
import logging

import structlog

from server._logging import configure_logging, get_logger


def test_get_logger_returns_structlog_logger():
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    assert isinstance(log, structlog.stdlib.BoundLogger) or hasattr(log, "info")


def test_configure_logging_emits_json(capsys):
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    log.info("hello", k="v")
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["k"] == "v"
    assert parsed["level"] == "info"


def test_configure_logging_console_mode_does_not_emit_json(capsys):
    configure_logging(level="INFO", json=False)
    log = get_logger("test")
    log.info("hello-console")
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    assert "hello-console" in line
    # console renderer is not JSON
    try:
        json.loads(line)
        raise AssertionError("expected non-JSON output in console mode")
    except json.JSONDecodeError:
        pass


def test_configure_logging_idempotent():
    configure_logging(level="INFO", json=True)
    configure_logging(level="INFO", json=True)
    log = get_logger("test")
    log.info("idempotent-ok")
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/test_logging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server._logging'`.

- [ ] **Step 3: Write `server/_logging.py`**

```python
import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json: bool = True) -> None:
    """Configure structlog + stdlib logging.

    Idempotent: safe to call multiple times.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
        force=True,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name else structlog.get_logger()
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest tests/test_logging.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Wire into `server/main.py`**

Modify `server/main.py`. Add at the top of `build_app()`:

```python
def build_app() -> Starlette:
    from server._logging import configure_logging
    from server.settings import get_settings

    settings = get_settings()
    configure_logging(level=settings.log_level, json=True)

    mcp = build_mcp()
    mcp_app = mcp.http_app()
    # ... rest unchanged
```

- [ ] **Step 6: Verify all tests still pass and the server starts cleanly**

Run:

```bash
uv run pytest -v
docker compose up -d postgres
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate uv run python -c "from server.main import build_app; build_app(); print('ok')"
```

Expected: 21 tests pass (17 + 4 new), build_app prints "ok".

- [ ] **Step 7: Commit**

```bash
git add server/_logging.py server/main.py tests/test_logging.py
git commit -m "feat: wire structlog with JSON output, configurable per env"
```

---

## Task 3: Provenance JSONB helpers

**Files:**
- Create: `ingest/_provenance.py`
- Create: `tests/test_ingest_provenance.py`

The provenance helper provides a typed builder for the JSONB structure stored on every record. Per spec §5.3:

```json
{
  "<field_name>": {
    "source": "sabin" | "climate_rights" | "c2li" | "melbourne" | "redline" | "manual",
    "retrieved_at": "2026-05-06T00:00:00Z",
    "upstream_version": "fixture-2026-05-06"
  }
}
```

- [ ] **Step 1: Write the failing test `tests/test_ingest_provenance.py`**

```python
from datetime import datetime, timezone

import pytest

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry


def test_provenance_entry_serializes_to_dict():
    entry = ProvenanceEntry(
        source="sabin",
        retrieved_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        upstream_version="fixture-2026-05-06",
    )
    d = entry.to_dict()
    assert d["source"] == "sabin"
    assert d["retrieved_at"] == "2026-05-06T12:00:00+00:00"
    assert d["upstream_version"] == "fixture-2026-05-06"


def test_provenance_builder_tracks_multiple_fields():
    entry = ProvenanceEntry(
        source="sabin",
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="v1",
    )
    pb = ProvenanceBuilder()
    pb.set("summary", entry)
    pb.set("status", entry)
    out = pb.build()
    assert set(out.keys()) == {"summary", "status"}
    assert out["summary"]["source"] == "sabin"
    assert out["status"]["upstream_version"] == "v1"


def test_provenance_builder_overwrite_replaces_entry():
    pb = ProvenanceBuilder()
    pb.set("summary", ProvenanceEntry("sabin", datetime(2026, 1, 1, tzinfo=timezone.utc), "v1"))
    pb.set("summary", ProvenanceEntry("manual", datetime(2026, 2, 1, tzinfo=timezone.utc), "v2"))
    out = pb.build()
    assert out["summary"]["source"] == "manual"
    assert out["summary"]["upstream_version"] == "v2"


def test_provenance_entry_invalid_source_raises():
    with pytest.raises(ValueError, match="invalid source"):
        ProvenanceEntry(
            source="bogus",
            retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
            upstream_version="v1",
        )
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/test_ingest_provenance.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write `ingest/_provenance.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ProvenanceSource = Literal[
    "sabin", "climate_rights", "c2li", "melbourne", "redline", "manual"
]
VALID_PROVENANCE_SOURCES: set[str] = {
    "sabin",
    "climate_rights",
    "c2li",
    "melbourne",
    "redline",
    "manual",
}


@dataclass(frozen=True)
class ProvenanceEntry:
    """A single field-level provenance record."""

    source: ProvenanceSource
    retrieved_at: datetime
    upstream_version: str

    def __post_init__(self) -> None:
        if self.source not in VALID_PROVENANCE_SOURCES:
            raise ValueError(
                f"invalid source: {self.source!r} "
                f"(must be one of {sorted(VALID_PROVENANCE_SOURCES)})"
            )
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "retrieved_at": self.retrieved_at.isoformat(),
            "upstream_version": self.upstream_version,
        }


@dataclass
class ProvenanceBuilder:
    """Accumulator for field-level provenance, serialised to a JSONB-shaped dict."""

    _entries: dict[str, ProvenanceEntry] = field(default_factory=dict)

    def set(self, field_name: str, entry: ProvenanceEntry) -> None:
        self._entries[field_name] = entry

    def build(self) -> dict[str, dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._entries.items()}
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest tests/test_ingest_provenance.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Verify all tests still pass + lint/type**

Run:

```bash
uv run pytest -v
uv run ruff check .
uv run pyright
```

Expected: 25 PASSED (17 + 4 + 4), all clean.

- [ ] **Step 6: Commit**

```bash
git add ingest/_provenance.py tests/test_ingest_provenance.py
git commit -m "feat: provenance builder with field-level source tags"
```

---

## Task 4: Sabin Pydantic models

**Files:**
- Create: `ingest/sabin/models.py`
- Create: `tests/test_ingest_sabin_models.py`

Models match the shape of one Sabin case as exposed in `climatecasechart.com`'s JSON. Hand-derived from inspecting the relaunched site's frontend payloads (Sept 2025 relaunch). Field set is the minimum needed for `get_case` to round-trip.

- [ ] **Step 1: Write the failing test `tests/test_ingest_sabin_models.py`**

```python
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.sabin.models import SabinCaseRecord, SabinDocument, SabinParty


def test_party_minimum_required_fields():
    p = SabinParty(name="Urgenda Foundation", side="plaintiff")
    assert p.name == "Urgenda Foundation"
    assert p.side == "plaintiff"
    assert p.party_type is None


def test_party_rejects_invalid_side():
    with pytest.raises(ValidationError):
        SabinParty(name="X", side="defendant_or_other")  # type: ignore[arg-type]


def test_document_minimum_required_fields():
    d = SabinDocument(
        title="District Court Decision",
        category="opinion",
        upstream_url="https://climatecasechart.com/case/urgenda/decision-1",
    )
    assert d.title == "District Court Decision"


def test_case_record_round_trips_from_fixture():
    fixture = Path("tests/fixtures/sabin_urgenda.json")
    if not fixture.exists():
        pytest.skip(f"fixture not yet authored: {fixture}")
    payload = json.loads(fixture.read_text())
    case = SabinCaseRecord.model_validate(payload)
    assert case.sabin_id is not None
    assert case.canonical_title
    assert case.jurisdiction_code == "NL"
    assert any(p.side == "plaintiff" for p in case.parties)
    assert any(p.side == "defendant" for p in case.parties)
    assert case.status_code in {"filed", "pending", "decided", "settled", "dismissed", "withdrawn"}
    assert len(case.documents) >= 1
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/test_ingest_sabin_models.py -v`
Expected: FAIL with ModuleNotFoundError. (The fixture-round-trip test will skip until Task 5.)

- [ ] **Step 3: Write `ingest/sabin/models.py`**

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

PartySide = Literal["plaintiff", "defendant", "intervenor", "amicus"]
PartyType = Literal["individual", "ngo", "corporation", "state", "sub_state"]
DocumentCategory = Literal[
    "opinion", "order", "complaint", "brief", "agency_record", "settlement", "judgment", "dissent"
]


class SabinParty(BaseModel):
    name: str
    side: PartySide
    party_type: PartyType | None = None


class SabinDocument(BaseModel):
    title: str
    category: DocumentCategory
    upstream_url: HttpUrl
    filed_date: date | None = None
    filed_by: str | None = None


class SabinCitationString(BaseModel):
    lang: str = Field(min_length=2, max_length=5)
    format: str
    text: str


class SabinCaseRecord(BaseModel):
    """The shape of one Sabin case as exposed by climatecasechart.com."""

    sabin_id: str
    canonical_title: str
    jurisdiction_code: str = Field(min_length=2, max_length=10)
    court_id: str | None = None
    filing_date: date | None = None
    decision_date: date | None = None
    status_code: str
    outcome_code: str | None = None
    summary: str | None = None
    summary_lang: str = "en"
    parties: list[SabinParty] = Field(default_factory=list)
    claim_types: list[str] = Field(default_factory=list)
    documents: list[SabinDocument] = Field(default_factory=list)
    citation_strings: list[SabinCitationString] = Field(default_factory=list)
    upstream_url: HttpUrl | None = None
```

- [ ] **Step 4: Run tests, expect PASS (one skipped)**

Run: `uv run pytest tests/test_ingest_sabin_models.py -v`
Expected: 3 PASSED, 1 SKIPPED (fixture).

- [ ] **Step 5: Verify all tests + lint + type**

Run:

```bash
uv run pytest -v
uv run ruff check .
uv run pyright
```

Expected: 28 PASSED, 1 SKIPPED, all clean.

- [ ] **Step 6: Commit**

```bash
git add ingest/sabin/models.py tests/test_ingest_sabin_models.py
git commit -m "feat: pydantic models for Sabin case records"
```

---

## Task 5: Hand-authored Urgenda JSON fixture

**Files:**
- Create: `tests/fixtures/sabin_urgenda.json`

This is the demo case. Real data, transcribed from the public Sabin record at `climatecasechart.com/case/urgenda-foundation-v-kingdom-of-the-netherlands/`. Transcribed manually so the fixture is reproducible without scraping.

- [ ] **Step 1: Create the fixture directory**

```bash
mkdir -p tests/fixtures
```

- [ ] **Step 2: Write `tests/fixtures/sabin_urgenda.json`**

```json
{
  "sabin_id": "urgenda-foundation-v-state-of-the-netherlands",
  "canonical_title": "Urgenda Foundation v. State of the Netherlands",
  "jurisdiction_code": "NL",
  "court_id": "nl-hoge-raad",
  "filing_date": "2013-11-20",
  "decision_date": "2019-12-20",
  "status_code": "decided",
  "outcome_code": "plaintiff_won",
  "summary": "Urgenda and 886 individual co-plaintiffs sued the Dutch state to compel emissions reductions of at least 25% below 1990 levels by 2020. The Hague District Court (2015) ordered the state to reduce emissions by 25% by end-2020. The Court of Appeal (2018) and the Supreme Court (Hoge Raad, 2019) affirmed. The Supreme Court grounded the order in articles 2 and 8 of the European Convention on Human Rights, finding the state had a positive obligation to protect the right to life and the right to family life from the dangers of climate change.",
  "summary_lang": "en",
  "parties": [
    {"name": "Urgenda Foundation", "side": "plaintiff", "party_type": "ngo"},
    {"name": "886 Individual Co-Plaintiffs", "side": "plaintiff", "party_type": "individual"},
    {"name": "State of the Netherlands", "side": "defendant", "party_type": "state"}
  ],
  "claim_types": [
    "human_rights",
    "constitutional",
    "tort"
  ],
  "documents": [
    {
      "title": "The Hague District Court Judgment (24 June 2015)",
      "category": "opinion",
      "upstream_url": "https://climatecasechart.com/non-us-case/urgenda-foundation-v-kingdom-of-the-netherlands/",
      "filed_date": "2015-06-24"
    },
    {
      "title": "The Hague Court of Appeal Judgment (9 October 2018)",
      "category": "opinion",
      "upstream_url": "https://climatecasechart.com/non-us-case/urgenda-foundation-v-kingdom-of-the-netherlands/",
      "filed_date": "2018-10-09"
    },
    {
      "title": "Hoge Raad (Supreme Court) Judgment (20 December 2019)",
      "category": "opinion",
      "upstream_url": "https://climatecasechart.com/non-us-case/urgenda-foundation-v-kingdom-of-the-netherlands/",
      "filed_date": "2019-12-20"
    }
  ],
  "citation_strings": [
    {"lang": "en", "format": "sabin", "text": "Urgenda Foundation v. State of the Netherlands, ECLI:NL:HR:2019:2007 (Hoge Raad, 20 Dec 2019)"},
    {"lang": "nl", "format": "native", "text": "HR 20 december 2019, ECLI:NL:HR:2019:2007 (Urgenda)"}
  ],
  "upstream_url": "https://climatecasechart.com/non-us-case/urgenda-foundation-v-kingdom-of-the-netherlands/"
}
```

- [ ] **Step 3: Re-run the model test now that the fixture exists**

Run: `uv run pytest tests/test_ingest_sabin_models.py -v`
Expected: 4 PASSED (no skips now — `test_case_record_round_trips_from_fixture` validates the fixture).

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/sabin_urgenda.json
git commit -m "test: hand-authored Urgenda Sabin fixture"
```

---

## Task 6: Migration 0008 — minimal vocabulary seed

**Files:**
- Create: `migrations/0008-seed-minimal-vocabularies.sql`
- Create: `tests/test_seed_vocabularies.py`

Seeds vocabulary values just sufficient to support the Urgenda fixture plus a small surrounding margin (so subsequent ad-hoc fixtures don't immediately break). Source is "manual" because the values are transcribed from Sabin's public taxonomy, not bulk-imported via API.

- [ ] **Step 1: Write the failing test `tests/test_seed_vocabularies.py`**

```python
import pytest

from server.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_minimum_vocabularies_seeded():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT code FROM vocabulary_jurisdiction WHERE code = 'NL'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT id FROM vocabulary_court WHERE id = 'nl-hoge-raad'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_status WHERE code = 'decided'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_outcome WHERE code = 'plaintiff_won'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_claim_type "
                "WHERE code IN ('human_rights', 'constitutional', 'tort') "
                "ORDER BY code"
            )
            rows = await cur.fetchall()
            assert [r[0] for r in rows] == ["constitutional", "human_rights", "tort"]

            await cur.execute(
                "SELECT code FROM vocabulary_document_category WHERE code = 'opinion'"
            )
            assert (await cur.fetchone()) is not None
    await close_pool()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_seed_vocabularies.py -v`
Expected: FAIL — vocabularies not yet seeded.

- [ ] **Step 3: Write `migrations/0008-seed-minimal-vocabularies.sql`**

```sql
-- Minimum vocabulary seed for the Urgenda demo case + small margin for adjacent test cases.
-- Source = 'manual' because values are transcribed from Sabin's public taxonomy.
-- Plan 3+ will replace this with a bulk import from Sabin/CPR.

INSERT INTO vocabulary_jurisdiction (code, name, kind, source, source_version) VALUES
    ('NL', 'Netherlands', 'national', 'manual', 'plan-2-seed'),
    ('US', 'United States', 'national', 'manual', 'plan-2-seed'),
    ('DE', 'Germany',       'national', 'manual', 'plan-2-seed'),
    ('GB', 'United Kingdom', 'national', 'manual', 'plan-2-seed'),
    ('AU', 'Australia',     'national', 'manual', 'plan-2-seed'),
    ('BR', 'Brazil',        'national', 'manual', 'plan-2-seed'),
    ('ICJ',    'International Court of Justice',         'international', 'manual', 'plan-2-seed'),
    ('IACTHR', 'Inter-American Court of Human Rights',  'international', 'manual', 'plan-2-seed'),
    ('ECTHR',  'European Court of Human Rights',        'international', 'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_court (id, name, jurisdiction_code, level, source, source_version) VALUES
    ('nl-hoge-raad',           'Hoge Raad der Nederlanden (Supreme Court of the Netherlands)', 'NL', 'supreme',   'manual', 'plan-2-seed'),
    ('nl-hof-den-haag',        'Gerechtshof Den Haag (The Hague Court of Appeal)',             'NL', 'appellate', 'manual', 'plan-2-seed'),
    ('nl-rechtbank-den-haag',  'Rechtbank Den Haag (The Hague District Court)',                'NL', 'trial',     'manual', 'plan-2-seed'),
    ('de-bverfg',              'Bundesverfassungsgericht (Federal Constitutional Court)',      'DE', 'supreme',   'manual', 'plan-2-seed'),
    ('us-scotus',              'Supreme Court of the United States',                           'US', 'supreme',   'manual', 'plan-2-seed'),
    ('icj-court',              'International Court of Justice',                               'ICJ', 'tribunal', 'manual', 'plan-2-seed'),
    ('iacthr-court',           'Inter-American Court of Human Rights',                         'IACTHR', 'tribunal', 'manual', 'plan-2-seed')
ON CONFLICT (id) DO NOTHING;

INSERT INTO vocabulary_claim_type (code, name, description, source, source_version) VALUES
    ('human_rights',     'Human rights',           'Claims grounded in domestic or international human-rights instruments',                  'manual', 'plan-2-seed'),
    ('constitutional',   'Constitutional',         'Claims grounded in national constitutional rights',                                       'manual', 'plan-2-seed'),
    ('tort',             'Tort / civil liability', 'Claims grounded in tort law (negligence, nuisance, public-trust, etc.)',                  'manual', 'plan-2-seed'),
    ('public_trust',     'Public trust doctrine',  'Claims grounded in the public-trust doctrine',                                            'manual', 'plan-2-seed'),
    ('regulatory_challenge', 'Regulatory challenge', 'Challenges to government action, inaction, or regulation under administrative law',     'manual', 'plan-2-seed'),
    ('corporate_accountability', 'Corporate accountability', 'Claims targeting corporate emissions, disclosure, or greenwashing',             'manual', 'plan-2-seed'),
    ('environmental_assessment', 'Environmental assessment', 'Procedural challenges to project approvals (NEPA / EIA / similar)',             'manual', 'plan-2-seed'),
    ('access_to_justice', 'Access to justice',     'Procedural cases about standing, intervention, or class-action access',                   'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_status (code, name, source, source_version) VALUES
    ('filed',     'Filed',     'manual', 'plan-2-seed'),
    ('pending',   'Pending',   'manual', 'plan-2-seed'),
    ('decided',   'Decided',   'manual', 'plan-2-seed'),
    ('settled',   'Settled',   'manual', 'plan-2-seed'),
    ('dismissed', 'Dismissed', 'manual', 'plan-2-seed'),
    ('withdrawn', 'Withdrawn', 'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_outcome (code, name, source, source_version) VALUES
    ('plaintiff_won',       'Plaintiff won',       'manual', 'plan-2-seed'),
    ('defendant_won',       'Defendant won',       'manual', 'plan-2-seed'),
    ('mixed',               'Mixed',               'manual', 'plan-2-seed'),
    ('settled_favorable',   'Settled favorably',   'manual', 'plan-2-seed'),
    ('settled_unfavorable', 'Settled unfavorably', 'manual', 'plan-2-seed'),
    ('na',                  'Not applicable',      'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_document_category (code, name, source, source_version) VALUES
    ('opinion',       'Opinion',       'manual', 'plan-2-seed'),
    ('order',         'Order',         'manual', 'plan-2-seed'),
    ('complaint',     'Complaint',     'manual', 'plan-2-seed'),
    ('brief',         'Brief',         'manual', 'plan-2-seed'),
    ('agency_record', 'Agency record', 'manual', 'plan-2-seed'),
    ('settlement',    'Settlement',    'manual', 'plan-2-seed'),
    ('judgment',      'Judgment',      'manual', 'plan-2-seed'),
    ('dissent',       'Dissent',       'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;
```

- [ ] **Step 4: Apply and verify**

Run:

```bash
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest tests/test_seed_vocabularies.py -v
```

Expected: 1 PASSED.

- [ ] **Step 5: Verify all tests + lint + type**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: 30 PASSED (29 prior + 1 new), all clean.

- [ ] **Step 6: Commit**

```bash
git add migrations/0008-seed-minimal-vocabularies.sql tests/test_seed_vocabularies.py
git commit -m "feat: migration 0008 — seed minimum vocabularies for demo cases"
```

---

## Task 7: Sabin → canonical schema parser

**Files:**
- Create: `ingest/sabin/parse.py`
- Create: `tests/test_ingest_sabin_parse.py`

Translates a `SabinCaseRecord` Pydantic model into the four canonical-schema dicts the UPSERT layer will consume: `case_dict`, `parties_list`, `claim_type_codes`, `citation_strings_list`, `documents_list`, plus a populated `ProvenanceBuilder`.

- [ ] **Step 1: Write the failing test `tests/test_ingest_sabin_parse.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import ParsedCase, parse_sabin_record


def test_parse_returns_canonical_dicts():
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed: ParsedCase = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="fixture-2026-05-06",
    )
    case = parsed.case
    assert case["sabin_id"] == "urgenda-foundation-v-state-of-the-netherlands"
    assert case["canonical_title"].startswith("Urgenda")
    assert case["jurisdiction_code"] == "NL"
    assert case["court_id"] == "nl-hoge-raad"
    assert case["status_code"] == "decided"
    assert case["outcome_code"] == "plaintiff_won"
    assert case["primary_source"] == "sabin"
    assert "summary" in case["provenance"]
    assert case["provenance"]["summary"]["source"] == "sabin"

    sides = sorted({p["side"] for p in parsed.parties})
    assert sides == ["defendant", "plaintiff"]
    assert all("ord" in p for p in parsed.parties)

    assert sorted(parsed.claim_type_codes) == ["constitutional", "human_rights", "tort"]

    assert len(parsed.documents) == 3
    assert all("upstream_url" in d for d in parsed.documents)
    assert parsed.documents[0]["category_code"] == "opinion"

    cs_langs = sorted({c["lang"] for c in parsed.citation_strings})
    assert cs_langs == ["en", "nl"]


def test_parse_assigns_sequential_ord_per_side():
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="v1",
    )
    plaintiff_ords = sorted(p["ord"] for p in parsed.parties if p["side"] == "plaintiff")
    defendant_ords = sorted(p["ord"] for p in parsed.parties if p["side"] == "defendant")
    assert plaintiff_ords == list(range(len(plaintiff_ords)))
    assert defendant_ords == list(range(len(defendant_ords)))
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_ingest_sabin_parse.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write `ingest/sabin/parse.py`**

```python
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry
from ingest.sabin.models import SabinCaseRecord


@dataclass
class ParsedCase:
    """Canonical dicts ready for UPSERT into the schema."""

    case: dict[str, Any]
    parties: list[dict[str, Any]]
    claim_type_codes: list[str]
    documents: list[dict[str, Any]]
    citation_strings: list[dict[str, Any]]


def parse_sabin_record(
    record: SabinCaseRecord, retrieved_at: datetime, upstream_version: str
) -> ParsedCase:
    """Translate a Sabin-shaped Pydantic model into canonical-schema dicts."""

    pb = ProvenanceBuilder()
    sabin_provenance = ProvenanceEntry(
        source="sabin", retrieved_at=retrieved_at, upstream_version=upstream_version
    )
    for field_name in (
        "canonical_title",
        "jurisdiction_code",
        "court_id",
        "filing_date",
        "decision_date",
        "status_code",
        "outcome_code",
        "summary",
    ):
        if getattr(record, field_name) is not None:
            pb.set(field_name, sabin_provenance)

    case: dict[str, Any] = {
        "sabin_id": record.sabin_id,
        "canonical_title": record.canonical_title,
        "jurisdiction_code": record.jurisdiction_code,
        "court_id": record.court_id,
        "filing_date": record.filing_date,
        "decision_date": record.decision_date,
        "status_code": record.status_code,
        "outcome_code": record.outcome_code,
        "summary": record.summary,
        "summary_lang": record.summary_lang,
        "primary_source": "sabin",
        "provenance": pb.build(),
    }

    side_counters: dict[str, int] = defaultdict(int)
    parties: list[dict[str, Any]] = []
    for party in record.parties:
        ord_value = side_counters[party.side]
        side_counters[party.side] += 1
        parties.append(
            {
                "side": party.side,
                "name": party.name,
                "party_type": party.party_type,
                "ord": ord_value,
            }
        )

    documents: list[dict[str, Any]] = []
    for doc in record.documents:
        documents.append(
            {
                "title": doc.title,
                "category_code": doc.category,
                "upstream_url": str(doc.upstream_url),
                "filed_date": doc.filed_date,
                "filed_by": doc.filed_by,
                "provenance": pb.build(),
            }
        )

    citation_strings: list[dict[str, Any]] = []
    for cs in record.citation_strings:
        citation_strings.append(
            {"lang": cs.lang, "format": cs.format, "text": cs.text}
        )

    return ParsedCase(
        case=case,
        parties=parties,
        claim_type_codes=list(record.claim_types),
        documents=documents,
        citation_strings=citation_strings,
    )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_ingest_sabin_parse.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Verify all tests + lint + type**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: 32 PASSED, all clean.

- [ ] **Step 6: Commit**

```bash
git add ingest/sabin/parse.py tests/test_ingest_sabin_parse.py
git commit -m "feat: parse Sabin records into canonical schema dicts with provenance"
```

---

## Task 8: Idempotent UPSERT into Postgres

**Files:**
- Create: `ingest/sabin/upsert.py`
- Create: `tests/test_ingest_sabin_upsert.py`

Inserts a `ParsedCase` into the database in a single transaction. Idempotent: re-running with the same `sabin_id` updates rather than duplicates. Children (parties, claim types, documents, citations) are deleted-then-reinserted within the transaction (the simplest correct approach for v0.1; can be optimised later).

- [ ] **Step 1: Write the failing test `tests/test_ingest_sabin_upsert.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import close_pool, get_pool


@pytest.fixture
async def parsed_urgenda():
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    return parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="fixture-2026-05-06",
    )


@pytest.mark.asyncio
async def test_upsert_inserts_new_case(parsed_urgenda):
    pool = await get_pool()
    case_id = await upsert_case(pool, parsed_urgenda)
    assert case_id is not None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT canonical_title FROM case_record WHERE id = %s", (case_id,)
            )
            row = await cur.fetchone()
            assert row is not None
            assert "Urgenda" in row[0]

            await cur.execute(
                "SELECT count(*) FROM case_party WHERE case_id = %s", (case_id,)
            )
            (n_parties,) = await cur.fetchone()
            assert n_parties == 3

            await cur.execute(
                "SELECT count(*) FROM case_claim_type WHERE case_id = %s", (case_id,)
            )
            (n_claims,) = await cur.fetchone()
            assert n_claims == 3

            await cur.execute(
                "SELECT count(*) FROM document WHERE case_id = %s", (case_id,)
            )
            (n_docs,) = await cur.fetchone()
            assert n_docs == 3

            await cur.execute(
                "SELECT count(*) FROM citation_string WHERE case_id = %s", (case_id,)
            )
            (n_cite,) = await cur.fetchone()
            assert n_cite == 2
    await close_pool()


@pytest.mark.asyncio
async def test_upsert_is_idempotent(parsed_urgenda):
    pool = await get_pool()
    case_id_1 = await upsert_case(pool, parsed_urgenda)
    case_id_2 = await upsert_case(pool, parsed_urgenda)
    assert case_id_1 == case_id_2

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(*) FROM case_record WHERE sabin_id = %s",
                (parsed_urgenda.case["sabin_id"],),
            )
            (n,) = await cur.fetchone()
            assert n == 1

            await cur.execute(
                "SELECT count(*) FROM case_party WHERE case_id = %s", (case_id_1,)
            )
            (n_parties,) = await cur.fetchone()
            assert n_parties == 3
    await close_pool()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_ingest_sabin_upsert.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write `ingest/sabin/upsert.py`**

```python
from typing import Any

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ingest.sabin.parse import ParsedCase


async def upsert_case(pool: AsyncConnectionPool, parsed: ParsedCase) -> str:
    """Insert or update a case, replacing all child rows. Returns the case UUID."""

    case = parsed.case
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO case_record (
                        sabin_id, canonical_title, jurisdiction_code, court_id,
                        filing_date, decision_date, status_code, outcome_code,
                        summary, summary_lang, primary_source, provenance, updated_at
                    )
                    VALUES (%(sabin_id)s, %(canonical_title)s, %(jurisdiction_code)s, %(court_id)s,
                            %(filing_date)s, %(decision_date)s, %(status_code)s, %(outcome_code)s,
                            %(summary)s, %(summary_lang)s, %(primary_source)s, %(provenance)s, now())
                    ON CONFLICT (sabin_id) DO UPDATE SET
                        canonical_title = EXCLUDED.canonical_title,
                        jurisdiction_code = EXCLUDED.jurisdiction_code,
                        court_id = EXCLUDED.court_id,
                        filing_date = EXCLUDED.filing_date,
                        decision_date = EXCLUDED.decision_date,
                        status_code = EXCLUDED.status_code,
                        outcome_code = EXCLUDED.outcome_code,
                        summary = EXCLUDED.summary,
                        summary_lang = EXCLUDED.summary_lang,
                        primary_source = EXCLUDED.primary_source,
                        provenance = EXCLUDED.provenance,
                        updated_at = now()
                    RETURNING id
                    """,
                    {**case, "provenance": Jsonb(case["provenance"])},
                )
                row = await cur.fetchone()
                assert row is not None
                case_id: str = str(row[0])

                await cur.execute("DELETE FROM case_party WHERE case_id = %s", (case_id,))
                await cur.execute(
                    "DELETE FROM case_claim_type WHERE case_id = %s", (case_id,)
                )
                await cur.execute("DELETE FROM document WHERE case_id = %s", (case_id,))
                await cur.execute(
                    "DELETE FROM citation_string WHERE case_id = %s", (case_id,)
                )

                for party in parsed.parties:
                    await cur.execute(
                        """
                        INSERT INTO case_party (case_id, side, name, party_type, ord)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (case_id, party["side"], party["name"], party["party_type"], party["ord"]),
                    )

                for claim_code in parsed.claim_type_codes:
                    await cur.execute(
                        """
                        INSERT INTO case_claim_type (case_id, claim_type_code)
                        VALUES (%s, %s)
                        """,
                        (case_id, claim_code),
                    )

                for doc in parsed.documents:
                    await cur.execute(
                        """
                        INSERT INTO document (
                            case_id, category_code, title, filed_date, filed_by,
                            upstream_url, provenance, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            case_id,
                            doc["category_code"],
                            doc["title"],
                            doc["filed_date"],
                            doc["filed_by"],
                            doc["upstream_url"],
                            Jsonb(doc["provenance"]),
                        ),
                    )

                for cs in parsed.citation_strings:
                    await cur.execute(
                        """
                        INSERT INTO citation_string (case_id, lang, format, text)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (case_id, cs["lang"], cs["format"], cs["text"]),
                    )

    return case_id
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_ingest_sabin_upsert.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Verify all tests + lint + type**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: 34 PASSED, all clean.

- [ ] **Step 6: Commit**

```bash
git add ingest/sabin/upsert.py tests/test_ingest_sabin_upsert.py
git commit -m "feat: idempotent UPSERT for Sabin cases with full child-row replacement"
```

---

## Task 9: `ingest_one` CLI entry point

**Files:**
- Create: `ingest/sabin/ingest_one.py`

Module-callable entry point: `python -m ingest.sabin.ingest_one path/to/fixture.json`. Loads JSON, validates with Pydantic, parses, upserts, logs the resulting case_id.

- [ ] **Step 1: Write `ingest/sabin/ingest_one.py`**

```python
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server._logging import configure_logging, get_logger
from server.db import close_pool, get_pool


async def ingest_one(fixture_path: Path, upstream_version: str) -> str:
    log = get_logger("ingest.sabin.ingest_one")
    payload = json.loads(fixture_path.read_text())
    record = SabinCaseRecord.model_validate(payload)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime.now(tz=timezone.utc),
        upstream_version=upstream_version,
    )
    pool = await get_pool()
    try:
        case_id = await upsert_case(pool, parsed)
    finally:
        await close_pool()
    log.info("case_upserted", sabin_id=record.sabin_id, case_id=case_id)
    return case_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one Sabin case from a JSON fixture.")
    parser.add_argument("path", type=Path, help="Path to the JSON fixture")
    parser.add_argument(
        "--upstream-version",
        default=f"manual-{datetime.now(tz=timezone.utc).date().isoformat()}",
        help="Upstream version label stored in provenance",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)
    case_id = asyncio.run(ingest_one(args.path, args.upstream_version))
    print(f"case_id={case_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run end-to-end against the Urgenda fixture**

Run:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
  uv run python -m ingest.sabin.ingest_one tests/fixtures/sabin_urgenda.json
```

Expected output (last line): `case_id=<some uuid>`.

- [ ] **Step 3: Verify the case was inserted**

Run:

```bash
docker compose exec postgres psql -U openclimate -d openclimate -c \
  "SELECT id, sabin_id, canonical_title FROM case_record WHERE sabin_id = 'urgenda-foundation-v-state-of-the-netherlands';"
```

Expected: one row showing the case.

- [ ] **Step 4: Verify `get_statistics` now reports 1 case**

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from server.tools.statistics import get_statistics

async def main():
    print(await get_statistics(scope="all"))

asyncio.run(main())
'
```

Expected: case_count: 1, document_count: 3, jurisdiction_count: 1.

- [ ] **Step 5: Lint + type**

Run: `uv run ruff check . && uv run pyright`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add ingest/sabin/ingest_one.py
git commit -m "feat: ingest_one CLI for single-case Sabin ingestion from a fixture"
```

---

## Task 10: `get_case` MCP tool

**Files:**
- Create: `server/tools/cases.py`
- Create: `tests/test_get_case_tool.py`
- Modify: `server/main.py` (register tool)

The `get_case(case_id_or_sabin_id)` tool returns the full case record: case fields + parties + claim types + documents + citation strings + provenance. Accepts EITHER the canonical UUID (`id`) OR the Sabin ID. Returns `None`-shaped error when not found.

- [ ] **Step 1: Write the failing test `tests/test_get_case_tool.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import close_pool, get_pool
from server.tools.cases import get_case


@pytest.fixture
async def upserted_urgenda_id():
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="fixture",
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    await close_pool()


@pytest.mark.asyncio
async def test_get_case_by_uuid(upserted_urgenda_id):
    result = await get_case(upserted_urgenda_id)
    assert result is not None
    assert "Urgenda" in result["canonical_title"]
    assert result["jurisdiction_code"] == "NL"
    assert len(result["parties"]) == 3
    assert sorted(result["claim_types"]) == ["constitutional", "human_rights", "tort"]
    assert len(result["documents"]) == 3
    assert len(result["citation_strings"]) == 2
    assert "provenance" in result


@pytest.mark.asyncio
async def test_get_case_by_sabin_id(upserted_urgenda_id):
    result = await get_case("urgenda-foundation-v-state-of-the-netherlands")
    assert result is not None
    assert "Urgenda" in result["canonical_title"]
    assert result["id"] == upserted_urgenda_id


@pytest.mark.asyncio
async def test_get_case_returns_none_when_not_found():
    result = await get_case("nonexistent-id")
    assert result is None
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_get_case_tool.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Write `server/tools/cases.py`**

```python
from typing import Any

from server.db import get_pool


async def get_case(case_id_or_sabin_id: str) -> dict[str, Any] | None:
    """Return a case record by canonical UUID or by Sabin ID, or None if not found."""

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, sabin_id, canonical_title, jurisdiction_code, court_id,
                       filing_date, decision_date, status_code, outcome_code,
                       summary, summary_lang, primary_source, provenance, updated_at
                FROM case_record
                WHERE id::text = %s OR sabin_id = %s
                """,
                (case_id_or_sabin_id, case_id_or_sabin_id),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            (
                _id, sabin_id, canonical_title, jurisdiction_code, court_id,
                filing_date, decision_date, status_code, outcome_code,
                summary, summary_lang, primary_source, provenance, updated_at,
            ) = row

            await cur.execute(
                """
                SELECT side, name, party_type, ord
                FROM case_party
                WHERE case_id = %s
                ORDER BY side, ord
                """,
                (str(_id),),
            )
            parties = [
                {"side": r[0], "name": r[1], "party_type": r[2], "ord": r[3]}
                for r in await cur.fetchall()
            ]

            await cur.execute(
                "SELECT claim_type_code FROM case_claim_type WHERE case_id = %s ORDER BY claim_type_code",
                (str(_id),),
            )
            claim_types = [r[0] for r in await cur.fetchall()]

            await cur.execute(
                """
                SELECT id, category_code, title, filed_date, filed_by, upstream_url, storage_url
                FROM document
                WHERE case_id = %s
                ORDER BY filed_date NULLS LAST, title
                """,
                (str(_id),),
            )
            documents = [
                {
                    "id": str(r[0]),
                    "category_code": r[1],
                    "title": r[2],
                    "filed_date": r[3].isoformat() if r[3] else None,
                    "filed_by": r[4],
                    "upstream_url": r[5],
                    "storage_url": r[6],
                }
                for r in await cur.fetchall()
            ]

            await cur.execute(
                "SELECT lang, format, text FROM citation_string WHERE case_id = %s ORDER BY lang, format",
                (str(_id),),
            )
            citation_strings = [
                {"lang": r[0], "format": r[1], "text": r[2]}
                for r in await cur.fetchall()
            ]

    return {
        "id": str(_id),
        "sabin_id": sabin_id,
        "canonical_title": canonical_title,
        "jurisdiction_code": jurisdiction_code,
        "court_id": court_id,
        "filing_date": filing_date.isoformat() if filing_date else None,
        "decision_date": decision_date.isoformat() if decision_date else None,
        "status_code": status_code,
        "outcome_code": outcome_code,
        "summary": summary,
        "summary_lang": summary_lang,
        "primary_source": primary_source,
        "provenance": provenance,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "parties": parties,
        "claim_types": claim_types,
        "documents": documents,
        "citation_strings": citation_strings,
    }
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_get_case_tool.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Register the tool with FastMCP in `server/main.py`**

Inside `build_mcp()`, after the `get_statistics` registration block, add:

```python
    from server.tools.cases import get_case as _get_case

    @mcp.tool(
        name="get_case",
        description=(
            "Return a full case record by canonical UUID or by Sabin ID. "
            "Includes parties, claim types, documents (with upstream URLs), "
            "citation strings, and field-level provenance. Returns null when no case matches."
        ),
    )
    async def get_case_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str,
    ) -> dict[str, object] | None:
        return await _get_case(case_id_or_sabin_id)
```

- [ ] **Step 6: Verify the tool is exposed via FastMCP Client**

Run:

```bash
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from fastmcp import Client
from server.main import build_mcp

async def main():
    mcp = build_mcp()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools])
        result = await client.call_tool("get_case", {"case_id_or_sabin_id": "urgenda-foundation-v-state-of-the-netherlands"})
        print("title:", result.structured_content["canonical_title"])

asyncio.run(main())
'
```

Expected:

```
tools: ['get_statistics', 'get_case']
title: Urgenda Foundation v. State of the Netherlands
```

- [ ] **Step 7: Verify all tests + lint + type**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: 37 PASSED (34 + 3), all clean.

- [ ] **Step 8: Commit**

```bash
git add server/tools/cases.py server/main.py tests/test_get_case_tool.py
git commit -m "feat: get_case MCP tool — fetch by UUID or Sabin ID"
```

---

## Task 11: End-to-end test (ingest + MCP query)

**Files:**
- Create: `tests/test_e2e_ingest_and_query.py`

Validates the full path: load fixture → parse → upsert → query via FastMCP Client → assert structure. Closes the loop on Plan 2.

- [ ] **Step 1: Write `tests/test_e2e_ingest_and_query.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastmcp import Client

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import close_pool, get_pool
from server.main import build_mcp


@pytest.mark.asyncio
async def test_ingest_then_query_via_mcp_client():
    # Ingest the Urgenda fixture
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        upstream_version="fixture-e2e",
    )
    case_id = await upsert_case(pool, parsed)

    # Query via FastMCP Client (in-process)
    mcp = build_mcp()
    async with Client(mcp) as client:
        # get_statistics should now show >=1 case, >=3 documents, >=1 jurisdiction
        stats = (await client.call_tool("get_statistics", {"scope": "all"})).structured_content
        assert stats["totals"]["case_count"] >= 1
        assert stats["totals"]["document_count"] >= 3
        assert stats["totals"]["jurisdiction_count"] >= 1

        # get_case by UUID
        case_by_uuid = (
            await client.call_tool("get_case", {"case_id_or_sabin_id": case_id})
        ).structured_content
        assert case_by_uuid is not None
        assert "Urgenda" in case_by_uuid["canonical_title"]

        # get_case by sabin_id
        case_by_sabin = (
            await client.call_tool(
                "get_case",
                {"case_id_or_sabin_id": "urgenda-foundation-v-state-of-the-netherlands"},
            )
        ).structured_content
        assert case_by_sabin is not None
        assert case_by_sabin["id"] == case_id
        assert sorted(case_by_sabin["claim_types"]) == ["constitutional", "human_rights", "tort"]
        assert case_by_sabin["status_code"] == "decided"
        assert case_by_sabin["outcome_code"] == "plaintiff_won"
        assert "summary" in case_by_sabin["provenance"]
        assert case_by_sabin["provenance"]["summary"]["source"] == "sabin"
    await close_pool()
```

- [ ] **Step 2: Run, expect PASS**

Run: `uv run pytest tests/test_e2e_ingest_and_query.py -v`
Expected: 1 PASSED.

- [ ] **Step 3: Verify all tests still pass + lint + type**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: 38 PASSED, all clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_ingest_and_query.py
git commit -m "test: e2e — ingest Urgenda fixture, query via FastMCP Client"
```

---

## Task 12: README update + Plan 2 wrap

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the full local workflow from a clean state**

```bash
docker compose down -v
docker compose up -d postgres
uv run yoyo apply --batch --database "postgresql://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest -v
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
  uv run python -m ingest.sabin.ingest_one tests/fixtures/sabin_urgenda.json
docker compose up -d --build server
sleep 3
DATABASE_URL=postgresql://openclimate:dev@localhost:5432/openclimate \
uv run python -c '
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools])
        case = await client.call_tool("get_case", {"case_id_or_sabin_id": "urgenda-foundation-v-state-of-the-netherlands"})
        print("title:", case.structured_content["canonical_title"])

asyncio.run(main())
'
```

Expected:
- All 38 tests pass
- ingest CLI prints `case_id=<uuid>`
- MCP smoke prints `tools: ['get_statistics', 'get_case']` and `title: Urgenda Foundation v. State of the Netherlands`

- [ ] **Step 2: Update `README.md` to add an Ingestion section**

Insert after the "Local development" section, before "Project status":

```markdown
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
        print(r.structured_content["canonical_title"])
asyncio.run(m())
'
```
```

Update the "Project status" section to:

```markdown
## Project status

Plans 1 and 2 complete: schema, MCP server, `get_statistics` and `get_case` tools, fixture-based Sabin ingestion (Urgenda v. Netherlands).
Next: Plan 2.5 — replace fixture with live Climate Policy Radar API client. See `docs/superpowers/plans/`.
```

- [ ] **Step 3: Tear down**

Run: `docker compose down`

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: Plan 2 — ingestion section + project status update"
```

---

## Verification checklist (post-Plan-2)

- [ ] All 38 tests pass; lint/format/typecheck clean.
- [ ] Migration 0008 (vocabulary seed) applies cleanly from scratch.
- [ ] `python -m ingest.sabin.ingest_one tests/fixtures/sabin_urgenda.json` succeeds and prints a UUID.
- [ ] `get_statistics(scope="all")` reports 1 case, 3 documents, 1 jurisdiction after ingestion.
- [ ] `get_case` returns Urgenda by both UUID and Sabin ID, with provenance, parties, claim types, documents, citation strings.
- [ ] FastMCP Client over HTTP at `http://localhost:8000/mcp` lists `get_statistics` and `get_case`.
- [ ] CI passes on push to the branch.

When all boxes are checked, Plan 2 is complete and Plan 2.5 (live Sabin/CPR API client to replace the fixture) becomes the next deliverable.
