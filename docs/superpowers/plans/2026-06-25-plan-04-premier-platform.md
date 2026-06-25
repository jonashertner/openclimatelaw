# OpenClimateLaw MCP — Plan 04: Premier Climate-Law Platform (Statement-Level Grounding)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This is a **master plan** spanning four largely independent tracks (A–D). Tracks **A** and **C** are execution-ready below. Tracks **B** and **D** are larger subsystems whose task-level detail is captured here but which should be expanded into their own dedicated full-TDD plans (`plan-05`, `plan-06`) at execution time (per the writing-plans Scope Check).

**Goal:** Bring OpenClimateLaw to opencaselaw.ch's grounding standard — every statement an AI writes is corroborated and referenced at the *passage* level — and close the data-quality gaps surfaced in live testing, so the platform is the premier global tool for climate-law researchers.

**Architecture:** Four tracks.
- **A — Search relevance & data hygiene:** FTS title-weighting so the named case wins; backfill the empty `parties` data; detect duplicate / multi-stage proceedings via the existing `merge_candidate` table.
- **B — Statement-level "pinpoint" grounding (flagship):** parse `document.text` into addressable passages with per-passage FTS + embeddings; add `find_relevant_passage` / `get_passage` tools that resolve a claim to one verbatim passage and *refuse to guess* when weak.
- **C — Harden the anti-hallucination contract:** 5-rail `attest_response`, independent-judge `check_claim_support`, and an MCP system-prompt contract (R1–R10 incl. claim-level sourcing + clickable links).
- **D — Trust & quality:** dataset-health checks + a hard publication gate + a public quality dashboard + a Climate Legal RAG Bench; (stretch) cryptographic provenance.

All patterns port directly from `caselaw-repo-1` (opencaselaw.ch): server-built citations, the R-rule contract, pinpoint Erwägung resolution, the 5-rail `attest_response`, the independent Sonnet judge, the publication gate, and RFC-6962 provenance.

**Tech Stack:** Python 3.14, uv, FastMCP, Postgres 16 + pgvector, `psycopg[binary,pool]`, yoyo-migrations, sentence-transformers (`all-MiniLM-L6-v2`, 384-dim), pymupdf; **new:** `anthropic` SDK (judge rails, Track C④ / D4).

## Global Constraints

- Python `>=3.14`; managed with `uv`. `ruff` line-length 100 (`select = E,F,I,B,UP,RUF`). `pyright` strict over `server`, `ingest`, `tests`. Note `server/tools/search.py`, `server/tools/related.py`, `ingest/citation_graph_titles.py` carry `# pyright: basic` — `reportCallIssue`/`reportArgumentType` still fire there, so any SQL passed to `cur.execute` must be a `LiteralString` (never an f-string; compose dynamic fragments from a `dict[str, LiteralString]` allowlist).
- CI gates (`.github/workflows/ci.yaml`) must stay green: `ruff check .`, `ruff format --check .`, `pyright`, `pytest -v`. All new work is **TDD** (red → green → commit).
- Tests run against an ephemeral Postgres and **assume an empty DB** (`tests/test_statistics.py::test_statistics_empty_database_returns_zeros`). Every test that seeds rows MUST clean them up (fixture `yield` + `DELETE ... WHERE sabin_id = ANY(...)`), as in `tests/test_get_case_tool.py` and `tests/test_search_cases_tool.py`.
- Migrations are forward-only (`yoyo`). All v0.1 tables exist (0001–0012). New structure goes in numbered migrations starting **0013**.
- The anti-hallucination contract is sacred: **never weaken R1/R2**; new rails are strictly additive. Any LLM-judge feature MUST degrade gracefully when `ANTHROPIC_API_KEY` is unset (return an advisory result, never raise/crash) — mirror the existing `check_claim_support` "no key" handling.
- New runtime dependency only via `pyproject.toml` + `uv lock`; pin a floor (`anthropic>=0.69`). Default judge model `claude-opus-4-8` (per the claude-api skill; configurable via env).
- Server-built-citations invariant: tools emit verbatim `citation_string`; the LLM never constructs one. Preserve this in every new tool.

---

## Track A — Search Relevance & Data Hygiene  *(execution-ready)*

**Objective:** the named case wins its own query; `parties` is populated; duplicate/multi-stage records are detected.

**Files:**
- Modify: `server/tools/search.py` (FTS weighting in `_SEARCH_SQL_HEAD`).
- Modify: `tests/test_search_cases_tool.py` (ranking tests).
- Create: `ingest/sabin/backfill_parties.py` (party backfill job).
- Create: `tests/test_backfill_parties.py`.
- Create: `ingest/dedup.py` (duplicate detector → `merge_candidate`).
- Create: `tests/test_dedup.py`.
- Reference (no change): `ingest/sabin/scraper.py`, `parse.py`, `upsert.py`, `models.py` (already extract + UPSERT parties); `migrations/0006-create-merge-candidate-table.sql` (the `merge_candidate` table already exists — reuse it).

### Task A1 — FTS title-weighting (fixes the Urgenda/KlimaSeniorinnen misrank)

**Interfaces:** Produces no new signature; changes only ranking inside `search_cases`.

Root cause (verified live): `to_tsvector('simple', canonical_title || ' ' || summary)` weights title and summary equally, so a case whose *summary* mentions "Urgenda" out-ranks the case *titled* "Urgenda" (it ranked #3). Fix: `setweight` the title to `'A'` and summary to `'D'`, and rank with `ts_rank('{0.1,0.2,0.4,1.0}', tsv, tsq)` so a title hit dominates.

- [ ] **Step 1 — failing test.** In `tests/test_search_cases_tool.py`, add to `_SEED` a title-bearing case and a decoy whose summary repeats the term, then:

```python
@pytest.mark.asyncio
async def test_title_match_outranks_summary_mention(seeded_cases: None) -> None:
    # Seed (add to fixture): a case TITLED "Greenpeace v. Example" and a decoy
    # whose summary repeatedly mentions "Greenpeace Example" but whose title does not.
    r = await search_cases("Greenpeace Example", semantic=False, limit=5)
    assert r["results"][0]["canonical_title"] == "Greenpeace v. Example"
```

- [ ] **Step 2 — run, expect FAIL** (`uv run pytest tests/test_search_cases_tool.py::test_title_match_outranks_summary_mention -v`): the decoy ranks first.
- [ ] **Step 3 — implement.** In `server/tools/search.py` `_SEARCH_SQL_HEAD`, define a weighted tsvector once and reuse it in `fts_rank`, the `GREATEST`, and the `WHERE @@`:

```sql
-- replace each `to_tsvector('simple', c.canonical_title || ' ' || coalesce(c.summary,''))`
-- with the weighted vector, and each `ts_rank(<tsv>, (SELECT tsq FROM q))`
-- with `ts_rank('{0.1,0.2,0.4,1.0}',
--               setweight(to_tsvector('simple', c.canonical_title), 'A')
--            || setweight(to_tsvector('simple', coalesce(c.summary,'')), 'D'),
--               (SELECT tsq FROM q))`
```

Keep this as a `LiteralString` (it already is — no f-string). The `* 10.0` scaling in `GREATEST` can drop to `* 4.0` once title weight carries the signal (tune with the test).

- [ ] **Step 4 — run, expect PASS**; run the full `tests/test_search_cases_tool.py` (17 + new) to confirm no regression.
- [ ] **Step 5 — commit** `feat(search): weight title matches above summary mentions (setweight A/D)`.
- [ ] **Step 6 — post-deploy live check** (after Track ships): `search_cases("Urgenda Netherlands")` → Urgenda #1; `search_cases("klimaseniorinnen")` → KlimaSeniorinnen in top 3.

### Task A2 — Backfill `parties` (case_party is empty: 0 rows for 5,027 cases)

**Interfaces:** Produces `backfill_parties(pool, *, limit=None, only_missing=True) -> dict[str,int]` (counts scanned/updated).

The CPR bulk path skips parties (`ingest/sabin/cpr.py:258`). The per-case Sabin path already parses + UPSERTs them (`scraper.py` → `parse.py:59` → `upsert.py:54 INSERT INTO case_party`). Backfill reuses that path for `primary_source='sabin'` cases with zero parties.

- [ ] **Step 1 — failing test** (`tests/test_backfill_parties.py`): seed a sabin case with 0 parties + a saved climatecasechart.com HTML fixture (`tests/fixtures/sabin_case_page.html`); assert backfill parses parties and `case_party` rows appear; clean up.
- [ ] **Step 2 — run, expect FAIL** (module missing).
- [ ] **Step 3 — implement** `ingest/sabin/backfill_parties.py`: query `case_record` where `primary_source='sabin'` AND `NOT EXISTS (SELECT 1 FROM case_party p WHERE p.case_id=c.id)`; for each, derive the climatecasechart.com slug from `primary_source`/`upstream_metadata`, fetch via `scraper.fetch_html`, extract the `__NEXT_DATA__` family, parse parties via the existing `parse.py` logic, UPSERT via the existing `upsert` party block. Rate-limit (≥1s), resumable (skip those now populated), `structlog` progress.
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat(ingest): backfill case parties from Sabin per-case pages`.
- [ ] **Step 6 — operational run** (separate, not in CI): run against prod corpus; re-check `get_case(...).parties` is populated; update `get_case` callers/docs.

### Task A3 — Duplicate / multi-stage detection → `merge_candidate`

**Interfaces:** Produces `detect_duplicates(pool) -> int` (candidates inserted). Reuses the existing `merge_candidate(case_id_a, case_id_b, score, features jsonb, status)` table.

1,089 records share a title (595 groups). Some are legitimate stages (trial/appeal); some are true dupes (the Urgenda title resolved to ≥2 records, fragmenting the citation graph). Detect, don't auto-merge.

- [ ] **Step 1 — failing test** (`tests/test_dedup.py`): seed three cases — two identical (same title, jurisdiction, decision_date) and one same-title-but-different-date; assert `detect_duplicates` inserts a `merge_candidate` for the identical pair (high score) and either none or a low-score row for the different-date pair; clean up.
- [ ] **Step 2 — run, expect FAIL.**
- [ ] **Step 3 — implement** `ingest/dedup.py`: group by `lower(canonical_title)`; for each intra-group pair compute `features` {title_exact, jurisdiction_match, date_delta_days, sabin_family_match} and a `score` (1.0 = same title+jurisdiction+date; lower as dates diverge → multi-stage); INSERT into `merge_candidate` (skip pairs already present). Never mutate `case_record`.
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat(ingest): detect duplicate/multi-stage cases into merge_candidate`.
- [ ] **Step 6 — follow-on (own task, optional):** an admin resolver + a `case_family` grouping so multi-stage proceedings cluster, and dedupe identical `(citing,cited)` display rows in `find_citations`/`find_cited_by` (surface court+date to disambiguate).

**Track A sequencing:** A1 (deploy immediately — pure win) → A2 → A3.

---

## Track C — Harden the Anti-Hallucination Contract  *(execution-ready)*

**Objective:** bring `attest_response`, `check_claim_support`, and the MCP system prompt to opencaselaw's depth.

**Files:**
- Modify: `server/tools/contracts/attest.py`, `server/tools/contracts/check_support.py`, `server/main.py`.
- Create: `server/tools/contracts/judge.py` (Anthropic judge helper, graceful no-key fallback).
- Modify: `tests/test_attest_response_tool.py`, `tests/test_check_claim_support_tool.py`; Create: `tests/test_judge.py`, `tests/test_mcp_instructions.py`.
- Modify: `pyproject.toml` (+`anthropic>=0.69`), then `uv lock`.

### Task C1 — MCP system-prompt contract (cheap, no new dep — do first)

`FastMCP(name="openclimatelaw")` ships **no `instructions`** today, so no R-rule contract reaches clients. Add one (ported/adapted from opencaselaw's `SYSTEM_PROMPT`, climate-specific): R1 never construct citations (use `cite`); R2 never quote unretrieved text (use `get_case`/`get_passage`/`check_claim_support`); R5 surface pending changes; **R10 claim-level sourcing** ("every concrete factual assertion about a climate case must point to its source"); clickable Markdown links; the `attest_response` workflow; "verifiability > veracity."

- [ ] **Step 1 — failing test** (`tests/test_mcp_instructions.py`):

```python
from server.main import build_mcp

def test_instructions_carry_the_contract():
    instr = build_mcp().instructions or ""
    for marker in ("R1", "R10", "verbatim", "attest_response", "citation"):
        assert marker in instr, marker
```

- [ ] **Step 2 — run, expect FAIL** (instructions is None).
- [ ] **Step 3 — implement:** add `instructions=CONTRACT` to `FastMCP(...)` in `build_mcp()`, `CONTRACT` a module constant with the rules.
- [ ] **Step 4 — PASS.** **Step 5 — commit** `feat(mcp): ship the R1–R10 anti-hallucination contract as server instructions`.

### Task C2 — `attest_response` rails ② (quote) and ③ (date) — no new dep

Extend `attest_response(draft_text, retrieved_ids, audit_quotes=False)` (keep current rail ① citation existence). Return `issues_by_category` + `linked_text`.

- [ ] **Step 1 — failing tests** (`tests/test_attest_response_tool.py`): (a) a draft with a quote NOT in any retrieved summary/document → flagged `quote_not_in_sources`; (b) a draft with a date adjacent to a citation that mismatches the case's `decision_date` → flagged `date_mismatch`; (c) `linked_text` wraps a valid citation in `[cite](url)`.
- [ ] **Step 2 — run, expect FAIL.**
- [ ] **Step 3 — implement** in `attest.py`: rail ② extract `"…"` spans ≥60 chars within `AUTHORITY_RADIUS≈250` chars of a citation; normalize whitespace/curly-quotes; verbatim-substring against the union of retrieved cases' `summary` + (when Track B lands) `document_passage.text` (until then: `summary` + `document.text` first 8k). Rail ③ find `DD.MM.YYYY`/ISO dates ≤60 chars from a citation; compare to stored `decision_date`/`filing_date`. Build `linked_text` wrapping each *valid* citation as a Markdown link to its canonical URL.
- [ ] **Step 4 — PASS.** **Step 5 — commit** `feat(contracts): attest_response quote + date rails + linked_text`.

### Task C3 — Independent judge: `check_claim_support` semantic mode + `attest_response` grounding rail ④

- [ ] **Step 1 — add dep:** `anthropic>=0.69` to `pyproject.toml`; `uv lock`; commit `chore: add anthropic SDK for grounding judge`.
- [ ] **Step 2 — failing test** (`tests/test_judge.py`, judge mocked): `judge_supports(claim, source_text)` returns `{verdict: "yes|partial|no|contradicts|unrelated", supporting_excerpt}`; with no `ANTHROPIC_API_KEY` returns `{verdict: "unavailable"}` (never raises).
- [ ] **Step 3 — implement** `server/tools/contracts/judge.py`: `anthropic.Anthropic()` (key from env), model `claude-opus-4-8`, a system prompt forcing "use ONLY the SOURCE TEXT; `supporting_excerpt` must be an exact substring of SOURCE or null." Graceful fallback when key/SDK missing.
- [ ] **Step 4 — wire** `check_claim_support(quote, source_id, source_kind, mode="verbatim")`: `mode="verbatim"` unchanged; `mode="judge"` fetches the source text and calls `judge_supports`. And `attest_response(..., audit_grounding=False)`: for each verified citation, extract the adjacent claim sentence and judge it against the cited summary/passage; flag `no/contradicts/unrelated` as `grounding`.
- [ ] **Step 5 — tests PASS** (mocked judge); **commit** `feat(contracts): independent-judge grounding (check_claim_support judge mode + attest rail ④)`.

**Track C sequencing:** C1 → C2 → C3.

---

## Track B — Statement-Level "Pinpoint" Grounding  *(flagship — expand into `plan-05` at execution)*

**Objective:** resolve any claim to the exact passage of a case document, with a stable citable ID, verbatim text, and a re-locatable anchor — refusing to guess when confidence is low. This is the literal implementation of "each statement corroborated and referenced."

**Schema — migration `0013-create-document-passage.sql`:**

```sql
CREATE TABLE document_passage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    para_index INTEGER NOT NULL,          -- stable ordinal within the document
    char_start INTEGER NOT NULL,          -- offset into document.text (re-location)
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,           -- sha256(text)
    embedding vector(384),                -- added once pgvector is enabled (it is)
    UNIQUE (document_id, para_index)
);
CREATE INDEX document_passage_case_idx ON document_passage(case_id);
CREATE INDEX document_passage_fts_idx ON document_passage USING GIN (to_tsvector('simple', text));
CREATE INDEX document_passage_hnsw_idx ON document_passage USING hnsw (embedding vector_cosine_ops);
```

**Files (per-track plan):** `ingest/passages.py` (splitter + embed + backfill), `server/tools/passages.py` (tools), register in `server/main.py`; tests `tests/test_passages_ingest.py`, `tests/test_passages_tool.py`.

**Tasks (task-level; full TDD in plan-05):**
1. Migration 0013 + a `test_migrations.py` assertion that `document_passage` exists.
2. `split_into_passages(text) -> list[(char_start, char_end, text)]`: paragraph splitter (double-newline, min length, merge short lines, drop boilerplate headers/footers). TDD on PDF-extracted fixtures.
3. `ingest/passages.py`: backfill over `document` rows `WHERE text IS NOT NULL` → rows in `document_passage`; embed in batches (`sentence-transformers`), resumable by `content_hash`.
4. `find_relevant_passage(case_id_or_sabin_id, claim, top_k=5)`: per-case two-pass FTS (`ts_rank`) + semantic (cosine) over `document_passage`; confidence gate = rank-gap × token-coverage (strip stopwords) with a cosine floor; return `matches[{document_id, para_index, text, highlighted_snippet (ts_headline), char_start, char_end, confidence, source}]` OR `{no_match: true, hint: "do not guess a passage"}`. **Refuse low confidence** (mirror opencaselaw `find_relevant_erwaegung`).
5. `get_passage(document_id, para_index)`: verbatim text + neighbours + the case `citation_string`.
6. Enrich `search_cases`/`get_case` results with a top-1 pinpoint passage (optional).
7. Use `document_passage.text` as the grounding source pool for Track C rails ② and ④ (replaces the first-8k-of-`document.text` interim).

**Risks:** noisy PDF paragraphing (splitter quality gates everything); embedding 64k docs (batch + resumable; ~hours, run as an operational job, not CI); 17k docs lack `text` (Track D backfill / re-extraction). Depends on nothing in A/C but is *improved* by A2/A3 (clean corpus) and *improves* C (passage-level grounding source).

---

## Track D — Trust & Quality Layer  *(expand into `plan-06`; partly operational)*

**Objective:** make correctness measurable, gated, and (stretch) cryptographically provable — the credibility layer of a "premier" platform.

**Tasks (task-level; full TDD in plan-06):**
- **D1 — Dataset-health checks** (`ingest/health/checks.py`): a registry of corpus checks each returning `{name, level: ok|warn|critical, value, detail}` — parties coverage, duplicate-title rate, citation-graph resolution %, doc-text coverage %, decision-date plausibility, embedding coverage, orphan rows, vocabulary FK integrity. TDD each against seeded fixtures. (Mirrors opencaselaw's 63-check L1.)
- **D2 — Publication gate** (`python -m ingest.health.gate`): runs checks; any `critical` exits non-zero. Wire into the ingestion refresh / `deploy/deploy.sh` as a pre-publish guard so a regressed corpus is never served (opencaselaw's hard L4 gate).
- **D3 — Quality dashboard:** a `get_quality_report` MCP tool returning the latest check results + a static `deploy/apex/quality.html` rendering them (publish-safe / blocked badge), mirroring opencaselaw's `quality.html`. Public claims must be dashboard-backed.
- **D4 — Climate Legal RAG Bench** (`benchmarks/`): N curated climate questions with gold answers + expected citations; run against the live stack + a judge; report correctness / groundedness / retrieval (model on Swiss Legal RAG Bench). Publish the numbers.
- **D5 — (Stretch) Cryptographic provenance** (`ingest/integrity.py`): RFC-6962 Merkle root over `(case_id, content_hash, decision_date)` committed to Git + anchored via OpenTimestamps; per-case inclusion-proof endpoint. Large; defer until A–C land.

**Risks:** judge cost/latency + key management (D4); defining "publish" for an in-place-updated prod DB (gate runs pre-refresh). Provenance (D5) is a multi-week effort — explicitly stretch.

---

## Sequencing & Milestones

- **M1 (immediate, low-risk, high-impact):** A1 (ranking → deploy) · C1 (instructions) · C2 (attest quote/date rails) · A2 (parties backfill) · A3 (dedup detection). Ships better search + a real contract + clean data with no new deps except none for A/C1/C2.
- **M2:** C3 (judge: `anthropic` dep, grounding rail + judge mode).
- **M3 (flagship):** Track B pinpoint passages (`plan-05`) — then point C's rails ②/④ at `document_passage`.
- **M4:** Track D trust/quality (`plan-06`); D5 provenance as stretch.

**Dependency summary:** A and C1/C2 are independent and immediate. C3 adds `anthropic`. B is independent but upgrades C's grounding source. D measures A/B/C and gates ingestion.

---

## Self-Review

- **Coverage vs the four approved tracks:** A (ranking + parties + dedup) ✓; B (pinpoint passages) ✓; C (5-rail attest + judge `check_claim_support` + system prompt) ✓; D (health checks + publication gate + dashboard + RAG bench + provenance) ✓.
- **Grounded in real code:** reuses the existing `merge_candidate` table (0006), the existing Sabin party path (`scraper`/`parse`/`upsert`), the `LiteralString` SQL constraint in `search.py`, the current `attest.py`/`check_support.py` signatures, and the absent `FastMCP(instructions=...)`.
- **Placeholders:** Tracks A and C carry concrete TDD steps with code/SQL. Tracks B and D are deliberately task-level here and flagged for dedicated full-TDD plans (`plan-05`, `plan-06`) per the writing-plans Scope Check — they are independent subsystems and each produces working software on its own.
- **Type consistency:** new signatures (`backfill_parties`, `detect_duplicates`, `judge_supports`, `find_relevant_passage`, `get_passage`, `attest_response(..., audit_quotes, audit_grounding)`, `check_claim_support(..., mode)`) are named consistently across tracks.
