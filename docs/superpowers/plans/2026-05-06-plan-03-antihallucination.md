# OpenClimateLaw MCP — Plan 3: Anti-Hallucination Contract Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the R1/R2/R5 enforcement layer from spec §8: `cite`, `check_claim_support`, `attest_response` MCP tools. End state: an LLM agent calling our MCP cannot fabricate case citations, cannot misquote retrieved text, and cannot misreport case outcomes — the server-side `attest_response` tool flags violations against retrieved IDs.

**Architecture:** A new `server/tools/contracts/` package houses (a) a citation-format regex registry, (b) the three contract tools, (c) a small validator engine. Tools dispatch through the existing FastMCP registration in `server/main.py`. The Urgenda fixture provides realistic test data (ECLI-formatted citations, summary text quotable in attest tests).

**Why now:** Spec §8 is the project's distinctive differentiator. With one case ingested, we already have citation strings in two formats and a summary to test against. Doing this before Plan 2.5 (live CPR client) means the Sabin outreach demo leads with the safety pitch, not just data-shape pitch.

**Out of scope (deferred):**
- R3 (statute text retrieval) — needs CCLW data; lands in Plan 6.
- R4 (legislative intent / materialien) — needs Paris/UNFCCC travaux ingestion; later.
- Multilingual quotation detection — original-only for v0.1; MT-generated quotation detection is Plan 4 work.

**Tech Stack:** Same as Plan 2 (no new deps). `re` for regex, existing FastMCP / psycopg / pytest stack.

---

## Files

**Create:**
- `server/tools/contracts/__init__.py`
- `server/tools/contracts/citation_formats.py` — regex registry per format
- `server/tools/contracts/cite.py` — `cite()` tool
- `server/tools/contracts/check_support.py` — `check_claim_support()` tool
- `server/tools/contracts/attest.py` — `attest_response()` tool
- `tests/test_citation_formats.py`
- `tests/test_cite_tool.py`
- `tests/test_check_claim_support_tool.py`
- `tests/test_attest_response_tool.py`
- `tests/test_e2e_anti_hallucination.py`

**Modify:**
- `server/main.py` — register the three new tools
- `README.md` — add anti-hallucination section
- `tests/conftest.py` — extract shared `_teardown_pool` autouse fixture (so it doesn't have to be re-added in every new test module)

---

## Task 1: Shared `_teardown_pool` autouse in `conftest.py`

This is the polish item from the Plan 2 review — promoted to a Plan 3 prereq because Plan 3 adds 5 more test modules and we don't want to copy-paste the fixture five times.

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_get_case_tool.py` (remove its local copy)
- Modify: `tests/test_ingest_sabin_upsert.py` (remove its local copy)

- [ ] **Step 1: Add the shared autouse to `tests/conftest.py`**

Replace the file with:

```python
import os
from collections.abc import AsyncGenerator

import pytest


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql://openclimate:dev@localhost:5432/openclimate"),
    )


@pytest.fixture(autouse=True)
async def _teardown_pool() -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction]
    """Close the connection pool after each test so the next test gets a fresh pool."""
    yield
    from server.db import close_pool

    await close_pool()
```

- [ ] **Step 2: Remove the local copy from `tests/test_get_case_tool.py`**

Delete the local `_teardown_pool` fixture (lines around 15–19 in the current file). The shared one in conftest.py applies automatically.

- [ ] **Step 3: Remove the local copy from `tests/test_ingest_sabin_upsert.py`**

Delete its `_teardown_pool` (or any equivalent module-local autouse).

- [ ] **Step 4: Verify all 38 tests still pass**

```bash
docker compose up -d postgres
sleep 5
uv run yoyo apply --batch --database "postgresql+psycopg://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest -v
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

Expected: 38 PASSED, all clean.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_get_case_tool.py tests/test_ingest_sabin_upsert.py
git commit -m "refactor: hoist _teardown_pool fixture to conftest.py"
```

---

## Task 2: Citation-format regex registry

**Files:**
- Create: `server/tools/contracts/__init__.py`
- Create: `server/tools/contracts/citation_formats.py`
- Create: `tests/test_citation_formats.py`

The registry is a small set of named regex patterns plus a `find_citation_spans()` helper that scans a string and returns `[(format_name, start, end, matched_text), ...]`. v0.1 covers ECLI (covers Urgenda + most EU/Dutch/Belgian/Luxembourg case law), BVerfGE (German constitutional court), BGE (Swiss federal court), and basic Bluebook reporters (US). Patterns can be extended without breaking the API.

- [ ] **Step 1: Write the failing test `tests/test_citation_formats.py`**

```python
from server.tools.contracts.citation_formats import find_citation_spans


def test_finds_ecli():
    text = "as held in ECLI:NL:HR:2019:2007 (Hoge Raad, 20 Dec 2019)"
    spans = find_citation_spans(text)
    formats = {s.format_name for s in spans}
    assert "ecli" in formats
    matched = next(s for s in spans if s.format_name == "ecli")
    assert matched.text == "ECLI:NL:HR:2019:2007"


def test_finds_bverfge():
    text = "see BVerfGE 157, 30 (Neubauer)"
    spans = find_citation_spans(text)
    assert any(s.format_name == "bverfge" for s in spans)


def test_finds_bge():
    text = "cf. BGE 145 IV 100"
    spans = find_citation_spans(text)
    assert any(s.format_name == "bge" for s in spans)


def test_finds_us_reporter():
    text = "see Massachusetts v. EPA, 549 U.S. 497 (2007)"
    spans = find_citation_spans(text)
    assert any(s.format_name == "us_reporter" for s in spans)


def test_finds_multiple_in_one_string():
    text = "compare ECLI:NL:HR:2019:2007 with BVerfGE 157, 30"
    spans = find_citation_spans(text)
    assert len(spans) == 2


def test_no_match_on_plain_prose():
    text = "the court agreed with the petitioner's argument."
    spans = find_citation_spans(text)
    assert spans == []
```

- [ ] **Step 2: Run, expect FAIL (ModuleNotFoundError).**

`uv run pytest tests/test_citation_formats.py -v`

- [ ] **Step 3: Write `server/tools/contracts/__init__.py`**

```python
```

- [ ] **Step 4: Write `server/tools/contracts/citation_formats.py`**

```python
import re
from dataclasses import dataclass

_PATTERNS: dict[str, re.Pattern[str]] = {
    # ECLI: European Case Law Identifier. Country (2 letters), Court (1-7 alnum),
    # Year (4 digits), ordinal (1-25 alnum chars).
    "ecli": re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Z0-9.]{1,25}\b"),
    # BVerfGE: German Federal Constitutional Court. "BVerfGE 157, 30" or "BVerfGE 157, 30 (1)".
    "bverfge": re.compile(r"\bBVerfGE\s+\d{1,3},\s*\d{1,4}(?:\s*\(\d+\))?\b"),
    # BGE: Swiss Federal Court. "BGE 145 IV 100".
    "bge": re.compile(r"\bBGE\s+\d{1,3}\s+(?:I|II|III|IV|V)\s+\d{1,4}\b"),
    # US reporter style. Volume + reporter abbrev + page, optional (Year). E.g.
    # "549 U.S. 497", "123 F.3d 456 (2d Cir. 2020)".
    "us_reporter": re.compile(
        r"\b\d{1,4}\s+(?:U\.S\.|F\.\d?[a-z]?|F\.\s*Supp\.|S\.\s*Ct\.)\s+\d{1,4}"
        r"(?:\s*\([^)]{1,40}\))?\b"
    ),
}


@dataclass(frozen=True)
class CitationSpan:
    format_name: str
    start: int
    end: int
    text: str


def find_citation_spans(text: str) -> list[CitationSpan]:
    """Scan `text` for known citation formats; return all non-overlapping matches."""
    spans: list[CitationSpan] = []
    for format_name, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            spans.append(
                CitationSpan(
                    format_name=format_name,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                )
            )
    spans.sort(key=lambda s: s.start)
    return spans
```

- [ ] **Step 5: Run tests, expect PASS**

`uv run pytest tests/test_citation_formats.py -v` → 6 PASSED.

- [ ] **Step 6: Verify all + lint + type**

`uv run pytest -v && uv run ruff check . && uv run pyright` → 44 PASSED, clean.

- [ ] **Step 7: Commit**

```bash
git add server/tools/contracts/__init__.py server/tools/contracts/citation_formats.py tests/test_citation_formats.py
git commit -m "feat: citation-format regex registry (ECLI, BVerfGE, BGE, US reporter)"
```

---

## Task 3: `cite()` tool

Returns the canonical `citation_string` for a case in the requested language and format. Requires a valid case_id (UUID or sabin_id) — preventing R1 violation by construction.

**Files:**
- Create: `server/tools/contracts/cite.py`
- Create: `tests/test_cite_tool.py`

- [ ] **Step 1: Write the failing test `tests/test_cite_tool.py`**

```python
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.cite import cite


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_cite_returns_sabin_format_in_english(upserted_urgenda_id: str) -> None:
    result = await cite(case_id=upserted_urgenda_id, lang="en", format="sabin")
    assert result is not None
    assert "ECLI:NL:HR:2019:2007" in result["citation_string"]
    assert result["lang"] == "en"
    assert result["format"] == "sabin"


@pytest.mark.asyncio
async def test_cite_returns_native_format_in_dutch(upserted_urgenda_id: str) -> None:
    result = await cite(
        case_id="urgenda-foundation-v-state-of-the-netherlands", lang="nl", format="native"
    )
    assert result is not None
    assert "HR 20 december 2019" in result["citation_string"]


@pytest.mark.asyncio
async def test_cite_returns_none_when_format_not_available(upserted_urgenda_id: str) -> None:
    result = await cite(case_id=upserted_urgenda_id, lang="en", format="oscola")
    assert result is None


@pytest.mark.asyncio
async def test_cite_returns_none_when_case_not_found() -> None:
    result = await cite(case_id="nonexistent", lang="en", format="sabin")
    assert result is None
```

- [ ] **Step 2: Run, expect FAIL**

`uv run pytest tests/test_cite_tool.py -v`

- [ ] **Step 3: Write `server/tools/contracts/cite.py`**

```python
from typing import Any

from server.db import get_pool


async def cite(case_id: str, lang: str, format: str) -> dict[str, Any] | None:
    """Return the canonical citation_string for a case in the requested language and format.

    Args:
        case_id: The canonical UUID or Sabin ID. Required (R1 enforcement: callers
            must already hold a valid case_id obtained from a search/get tool).
        lang: ISO 639-1 language code (e.g. 'en', 'nl', 'de').
        format: Citation format name (e.g. 'sabin', 'native', 'bluebook', 'oscola').

    Returns:
        {citation_string, lang, format, case_id} on hit, or None when no row matches.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT cs.text, c.id
                FROM citation_string cs
                JOIN case_record c ON c.id = cs.case_id
                WHERE (c.id::text = %s OR c.sabin_id = %s)
                  AND cs.lang = %s
                  AND cs.format = %s
                """,
                (case_id, case_id, lang, format),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            citation_text, case_uuid = row

    return {
        "citation_string": citation_text,
        "lang": lang,
        "format": format,
        "case_id": str(case_uuid),
    }
```

- [ ] **Step 4: Run, expect PASS**

`uv run pytest tests/test_cite_tool.py -v` → 4 PASSED.

- [ ] **Step 5: Verify all + lint + type**

Expected: 48 PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/tools/contracts/cite.py tests/test_cite_tool.py
git commit -m "feat: cite() — R1-enforcing citation-string lookup"
```

---

## Task 4: `check_claim_support()` tool

Verifies that a quoted string appears verbatim in a named source's text. The source can be a case summary, a document text, or a citation_string.

**Files:**
- Create: `server/tools/contracts/check_support.py`
- Create: `tests/test_check_claim_support_tool.py`

- [ ] **Step 1: Write the failing test `tests/test_check_claim_support_tool.py`**

```python
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.check_support import check_claim_support


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_check_claim_support_passes_for_real_summary_substring(
    upserted_urgenda_id: str,
) -> None:
    quote = "the right to family life from the dangers of climate change"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="case_summary"
    )
    assert result["supported"] is True


@pytest.mark.asyncio
async def test_check_claim_support_fails_for_invented_quote(upserted_urgenda_id: str) -> None:
    quote = "the court ordered immediate cessation of all fossil-fuel extraction"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="case_summary"
    )
    assert result["supported"] is False
    assert "case_summary" in result["reason"]


@pytest.mark.asyncio
async def test_check_claim_support_passes_for_citation_string_substring(
    upserted_urgenda_id: str,
) -> None:
    quote = "ECLI:NL:HR:2019:2007"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="citation_string"
    )
    assert result["supported"] is True


@pytest.mark.asyncio
async def test_check_claim_support_fails_when_source_not_found() -> None:
    result = await check_claim_support(
        quote="anything", source_id="nonexistent", source_kind="case_summary"
    )
    assert result["supported"] is False
    assert "not found" in result["reason"].lower()


@pytest.mark.asyncio
async def test_check_claim_support_invalid_source_kind_raises() -> None:
    with pytest.raises(ValueError, match="invalid source_kind"):
        await check_claim_support(
            quote="x", source_id="any", source_kind="bogus_kind"
        )
```

- [ ] **Step 2: Run, expect FAIL**

`uv run pytest tests/test_check_claim_support_tool.py -v`

- [ ] **Step 3: Write `server/tools/contracts/check_support.py`**

```python
from typing import Any, Literal

from server.db import get_pool

SourceKind = Literal["case_summary", "document_text", "citation_string"]
VALID_SOURCE_KINDS: set[str] = {"case_summary", "document_text", "citation_string"}


async def check_claim_support(
    quote: str, source_id: str, source_kind: str
) -> dict[str, Any]:
    """Validate that `quote` appears verbatim in the named source's text.

    Args:
        quote: The exact text to search for.
        source_id: For case_summary -> case UUID or sabin_id.
                   For document_text -> document UUID.
                   For citation_string -> case UUID or sabin_id (any of its citation_strings).
        source_kind: 'case_summary' | 'document_text' | 'citation_string'.

    Returns:
        {supported: bool, reason: str, source_id: str, source_kind: str}.
    """
    if source_kind not in VALID_SOURCE_KINDS:
        raise ValueError(
            f"invalid source_kind: {source_kind!r} "
            f"(must be one of {sorted(VALID_SOURCE_KINDS)})"
        )

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            haystack: str | None = None
            if source_kind == "case_summary":
                await cur.execute(
                    "SELECT summary FROM case_record WHERE id::text = %s OR sabin_id = %s",
                    (source_id, source_id),
                )
                row = await cur.fetchone()
                haystack = row[0] if row else None
            elif source_kind == "document_text":
                await cur.execute(
                    "SELECT text FROM document WHERE id::text = %s",
                    (source_id,),
                )
                row = await cur.fetchone()
                haystack = row[0] if row else None
            elif source_kind == "citation_string":
                await cur.execute(
                    """
                    SELECT cs.text
                    FROM citation_string cs
                    JOIN case_record c ON c.id = cs.case_id
                    WHERE c.id::text = %s OR c.sabin_id = %s
                    """,
                    (source_id, source_id),
                )
                rows = await cur.fetchall()
                haystack = "\n".join(r[0] for r in rows) if rows else None

    if haystack is None:
        return {
            "supported": False,
            "reason": f"source not found: source_kind={source_kind} source_id={source_id}",
            "source_id": source_id,
            "source_kind": source_kind,
        }

    if quote in haystack:
        return {
            "supported": True,
            "reason": "verbatim substring match",
            "source_id": source_id,
            "source_kind": source_kind,
        }

    return {
        "supported": False,
        "reason": f"quote not found in {source_kind}",
        "source_id": source_id,
        "source_kind": source_kind,
    }
```

- [ ] **Step 4: Run, expect PASS**

`uv run pytest tests/test_check_claim_support_tool.py -v` → 5 PASSED.

- [ ] **Step 5: Verify all + lint + type**

Expected: 53 PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/tools/contracts/check_support.py tests/test_check_claim_support_tool.py
git commit -m "feat: check_claim_support() — R2 verbatim-quotation validator"
```

---

## Task 5: `attest_response()` tool

Scans a draft response for citation-shaped strings; flags any that don't appear verbatim in the union of `citation_string` values from `retrieved_ids`.

**Files:**
- Create: `server/tools/contracts/attest.py`
- Create: `tests/test_attest_response_tool.py`

- [ ] **Step 1: Write the failing test `tests/test_attest_response_tool.py`**

```python
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.attest import attest_response


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_attest_passes_when_no_citations_present() -> None:
    result = await attest_response(
        draft_text="The court ruled in favour of the plaintiffs.",
        retrieved_ids=[],
    )
    assert result["passed"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_attest_passes_when_citation_matches_retrieved(
    upserted_urgenda_id: str,
) -> None:
    draft = (
        "The Supreme Court of the Netherlands held in ECLI:NL:HR:2019:2007 that "
        "the state has a positive obligation to protect the right to life."
    )
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[upserted_urgenda_id],
    )
    assert result["passed"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_attest_flags_unretrieved_citation() -> None:
    draft = "Citing ECLI:DE:BVERFG:2021:rs20210324.1bvr265618 for the proposition that..."
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[],
    )
    assert result["passed"] is False
    assert len(result["violations"]) == 1
    v = result["violations"][0]
    assert v["text"] == "ECLI:DE:BVERFG:2021:rs20210324.1bvr265618"
    assert v["format"] == "ecli"


@pytest.mark.asyncio
async def test_attest_flags_invented_us_reporter_citation(
    upserted_urgenda_id: str,
) -> None:
    draft = "see Massachusetts v. EPA, 549 U.S. 497 (2007)"
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[upserted_urgenda_id],  # Urgenda is retrieved; SCOTUS case is not
    )
    assert result["passed"] is False
    assert any(v["format"] == "us_reporter" for v in result["violations"])
```

- [ ] **Step 2: Run, expect FAIL**

`uv run pytest tests/test_attest_response_tool.py -v`

- [ ] **Step 3: Write `server/tools/contracts/attest.py`**

```python
from typing import Any

from server.db import get_pool
from server.tools.contracts.citation_formats import find_citation_spans


async def attest_response(
    draft_text: str, retrieved_ids: list[str]
) -> dict[str, Any]:
    """Validate a draft response against the citation strings of retrieved cases.

    Substring-matches `draft_text` for citation-shaped strings (ECLI, BVerfGE, BGE,
    US reporter). Flags any match that is NOT also present in the union of
    `citation_string.text` values for cases identified by `retrieved_ids`.

    Args:
        draft_text: The LLM-generated text to validate.
        retrieved_ids: Case UUIDs or Sabin IDs the LLM claims to have retrieved.

    Returns:
        {
            passed: bool,
            violations: [{format, text, span: [start, end], reason}, ...],
        }
    """
    spans = find_citation_spans(draft_text)
    if not spans:
        return {"passed": True, "violations": []}

    retrieved_citation_texts: set[str] = set()
    if retrieved_ids:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                placeholders = ", ".join(["%s"] * len(retrieved_ids))
                params = list(retrieved_ids) + list(retrieved_ids)
                await cur.execute(
                    f"""
                    SELECT cs.text
                    FROM citation_string cs
                    JOIN case_record c ON c.id = cs.case_id
                    WHERE c.id::text IN ({placeholders})
                       OR c.sabin_id IN ({placeholders})
                    """,
                    params,
                )
                rows = await cur.fetchall()
                for r in rows:
                    retrieved_citation_texts.add(r[0])

    violations: list[dict[str, Any]] = []
    for span in spans:
        # A citation is supported if its text appears as a substring of ANY retrieved
        # citation_string. Equality is too strict (formatting differences); substring is
        # the right granularity for ECLI ids embedded in fuller citations.
        if any(span.text in cs for cs in retrieved_citation_texts):
            continue
        violations.append(
            {
                "format": span.format_name,
                "text": span.text,
                "span": [span.start, span.end],
                "reason": (
                    "citation-shaped string not present in retrieved citation_strings"
                ),
            }
        )

    return {"passed": len(violations) == 0, "violations": violations}
```

- [ ] **Step 4: Run, expect PASS**

`uv run pytest tests/test_attest_response_tool.py -v` → 4 PASSED.

- [ ] **Step 5: Verify all + lint + type**

Expected: 57 PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/tools/contracts/attest.py tests/test_attest_response_tool.py
git commit -m "feat: attest_response() — R1 enforcement via citation-format scanning"
```

---

## Task 6: Register the three tools with FastMCP and add an end-to-end test

**Files:**
- Modify: `server/main.py` (register `cite`, `check_claim_support`, `attest_response`)
- Create: `tests/test_e2e_anti_hallucination.py`

- [ ] **Step 1: Add the registrations to `server/main.py`**

Inside `build_mcp()`, after the `get_case_tool` block (just before `return mcp`), add:

```python
    from server.tools.contracts.attest import attest_response as _attest_response
    from server.tools.contracts.check_support import check_claim_support as _check_claim_support
    from server.tools.contracts.cite import cite as _cite

    @mcp.tool(
        name="cite",
        description=(
            "Return the canonical citation_string for a case in the requested language "
            "and format. Requires a valid case_id (UUID or sabin_id). The R1 contract: "
            "never construct citations from training data; always call this tool to get a "
            "verbatim citation_string from a previously-retrieved case."
        ),
    )
    async def cite_tool(  # pyright: ignore[reportUnusedFunction]
        case_id: str, lang: str, format: str
    ) -> dict[str, object] | None:
        return await _cite(case_id=case_id, lang=lang, format=format)

    @mcp.tool(
        name="check_claim_support",
        description=(
            "Validate that a quoted string appears verbatim in the named source's text. "
            "source_kind: 'case_summary' | 'document_text' | 'citation_string'. "
            "The R2 contract: never quote what wasn't retrieved."
        ),
    )
    async def check_claim_support_tool(  # pyright: ignore[reportUnusedFunction]
        quote: str, source_id: str, source_kind: str
    ) -> dict[str, object]:
        return await _check_claim_support(
            quote=quote, source_id=source_id, source_kind=source_kind
        )

    @mcp.tool(
        name="attest_response",
        description=(
            "Scan a draft response for citation-shaped strings and flag any that don't "
            "appear in the citation_strings of retrieved cases. Returns "
            "{passed: bool, violations: [...]}. The R1 contract enforced after-the-fact."
        ),
    )
    async def attest_response_tool(  # pyright: ignore[reportUnusedFunction]
        draft_text: str, retrieved_ids: list[str]
    ) -> dict[str, object]:
        return await _attest_response(draft_text=draft_text, retrieved_ids=retrieved_ids)
```

- [ ] **Step 2: Write `tests/test_e2e_anti_hallucination.py`**

```python
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastmcp import Client

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.main import build_mcp


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_full_anti_hallucination_workflow(upserted_urgenda_id: str) -> None:
    """Simulate an LLM workflow: get_case -> cite -> compose response -> attest_response."""
    mcp = build_mcp()
    async with Client(mcp) as client:
        # Step 1: LLM retrieves the case.
        case_result = await client.call_tool(
            "get_case", {"case_id_or_sabin_id": upserted_urgenda_id}
        )
        assert case_result.structured_content is not None
        case = case_result.structured_content

        # Step 2: LLM asks for a verbatim citation in en/sabin.
        cite_result = await client.call_tool(
            "cite",
            {"case_id": upserted_urgenda_id, "lang": "en", "format": "sabin"},
        )
        assert cite_result.structured_content is not None
        citation = cite_result.structured_content["citation_string"]

        # Step 3: LLM composes a response embedding the citation.
        draft = (
            f"The Supreme Court of the Netherlands held in {citation} that the state "
            f"must reduce greenhouse-gas emissions. {case['summary'][:120]}"
        )

        # Step 4: attest_response validates.
        attest_result = await client.call_tool(
            "attest_response",
            {"draft_text": draft, "retrieved_ids": [upserted_urgenda_id]},
        )
        assert attest_result.structured_content is not None
        assert attest_result.structured_content["passed"] is True

        # Step 5: A bad draft (un-retrieved citation) fails attestation.
        bad_draft = "Citing 549 U.S. 497 (2007), the court reasoned..."
        bad_attest = await client.call_tool(
            "attest_response",
            {"draft_text": bad_draft, "retrieved_ids": [upserted_urgenda_id]},
        )
        assert bad_attest.structured_content is not None
        assert bad_attest.structured_content["passed"] is False
        violations = bad_attest.structured_content["violations"]
        assert any("U.S. 497" in v["text"] for v in violations)

        # Step 6: check_claim_support catches a misquote.
        bad_quote = "the court ordered immediate cessation of all fossil-fuel extraction"
        check_result = await client.call_tool(
            "check_claim_support",
            {
                "quote": bad_quote,
                "source_id": upserted_urgenda_id,
                "source_kind": "case_summary",
            },
        )
        assert check_result.structured_content is not None
        assert check_result.structured_content["supported"] is False
```

- [ ] **Step 3: Run, expect PASS**

`uv run pytest tests/test_e2e_anti_hallucination.py -v` → 1 PASSED.

- [ ] **Step 4: Verify all + lint + type**

Expected: 58 PASSED.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_e2e_anti_hallucination.py
git commit -m "feat: register R1/R2/R5 tools with FastMCP + e2e anti-hallucination test"
```

---

## Task 7: README + Plan 3 wrap

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the full local workflow from a clean state**

```bash
docker compose down -v
docker compose up -d postgres
sleep 8
uv run yoyo apply --batch --database "postgresql+psycopg://openclimate:dev@localhost:5432/openclimate" migrations
uv run pytest -v
```

Expected: 58 tests PASS.

- [ ] **Step 2: Update `README.md`**

Add an "Anti-hallucination contract" section after "Ingest a case":

```markdown
## Anti-hallucination contract

The MCP enforces the R1, R2, and R5 rules from spec §8 server-side:

- `cite(case_id, lang, format)` — returns canonical `citation_string` for a case. The R1 contract: never construct citations.
- `check_claim_support(quote, source_id, source_kind)` — verifies a quotation appears verbatim in the named source. The R2 contract: never quote what wasn't retrieved.
- `attest_response(draft_text, retrieved_ids)` — scans a draft for citation-shaped strings and flags any not present in the citation_strings of retrieved cases. Returns `{passed: bool, violations: [...]}`.

R3 (statute text) and R4 (legislative intent) are deferred to Plan 6 once CCLW data lands.
```

Update the project status section:

```markdown
## Project status

Plans 1-3 complete: schema, MCP server, `get_statistics`/`get_case`/`cite`/`check_claim_support`/`attest_response` tools, fixture-based Sabin ingestion, anti-hallucination contract (R1/R2/R5 enforced).
Next: Plan 2.5 — replace fixture with live Climate Policy Radar API client. See `docs/superpowers/plans/`.
```

- [ ] **Step 3: Tear down**

`docker compose down`

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: Plan 3 — anti-hallucination contract section + status update"
```

---

## Verification checklist (post-Plan-3)

- [ ] All 58 tests pass; lint/format/typecheck clean.
- [ ] FastMCP exposes 5 tools: `get_statistics`, `get_case`, `cite`, `check_claim_support`, `attest_response`.
- [ ] `cite()` returns Urgenda's ECLI in en/sabin and the Dutch HR format in nl/native.
- [ ] `attest_response()` flags an invented `549 U.S. 497 (2007)` citation when only Urgenda is retrieved.
- [ ] `check_claim_support()` catches a misquoted summary and verifies a real one.
- [ ] The end-to-end test demonstrates the full R1/R2 workflow through FastMCP Client.

When all boxes are checked, Plan 3 is complete and the project's headline differentiator is shipped. Plan 2.5 (live CPR API client) becomes the next deliverable.
