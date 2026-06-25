# OpenClimateLaw MCP — Plan 05: Statement-Level Pinpoint Passages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. This is Track B of plan-04, expanded.

**Goal:** Resolve any claim to the *exact passage* of a case's decision text — returning verbatim text, a stable citable pinpoint, a confidence score, and a re-locatable anchor — and **refuse to guess** when no passage clearly matches. So every statement can be corroborated against a precise passage, not just a whole document.

**Architecture:** A new `document_passage` table holds paragraph-sized units of `document.text` (char offsets preserved) with per-passage FTS + pgvector embeddings. A splitter parses `document.text` into passages. `find_relevant_passage(case, claim)` ranks a case's passages (lexical FTS + semantic cosine) behind a confidence gate; `get_passage(document_id, para_index)` returns verbatim text + neighbours. Builds on the already-shipped `get_document_text` and the existing sentence-transformers / pgvector stack. Ports opencaselaw.ch's `find_relevant_erwaegung` pattern (confidence-gated, refuses low-confidence) to climate decisions.

**Tech Stack:** Python 3.14, uv, FastMCP, Postgres 16 + pgvector, psycopg, yoyo-migrations, sentence-transformers (`all-MiniLM-L6-v2`, 384-dim).

## Global Constraints

- TDD throughout; CI green (`ruff check`, `ruff format --check`, `pyright` strict, `pytest`). Tests seed + clean up (empty-DB assumption).
- SQL passed to `cur.execute` must be `LiteralString`; compose any dynamic ORDER BY from a `dict[str, LiteralString]` allowlist (see `server/tools/search.py`).
- Migrations forward-only; next number is **0013**.
- Lexical FTS path must work **without** embeddings (so the tools are functional immediately after a text-only backfill; embeddings are an enhancement run separately).
- The 64k-document backfill is an **operational** job (script + flag), not run in CI.
- Confidence gate must **refuse** (return `no_match`) rather than return a weak guess — mirrors opencaselaw `find_relevant_erwaegung`.

---

### Task 1: Migration `0013` — `document_passage`

**Files:** Create `migrations/0013-create-document-passage.sql`; Modify `tests/test_migrations.py`.

```sql
CREATE TABLE document_passage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    para_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector(384),
    UNIQUE (document_id, para_index)
);
CREATE INDEX document_passage_case_idx ON document_passage(case_id);
CREATE INDEX document_passage_fts_idx ON document_passage
    USING GIN (to_tsvector('simple', text));
CREATE INDEX document_passage_hnsw_idx ON document_passage
    USING hnsw (embedding vector_cosine_ops);
```

- [ ] Step 1: write the migration file above.
- [ ] Step 2: add `test_document_passage_table_exists` to `tests/test_migrations.py` (query `information_schema.columns` for the table). Run → FAIL.
- [ ] Step 3: `uv run yoyo apply --batch --database "postgresql+psycopg://openclimate:dev@localhost:5432/openclimate" migrations`. Re-run test → PASS.
- [ ] Step 4: commit `feat(db): document_passage table (0013)`.

### Task 2: Passage splitter

**Files:** Create `ingest/passages.py`; Create `tests/test_passages_split.py`.

**Interfaces:** Produces `split_into_passages(text: str) -> list[tuple[int, int, str]]` — `(char_start, char_end, text)` per passage, offsets into the original `text`.

- [ ] Step 1 (test): blank-line-separated paragraphs are split; fragments `< _MIN_PASSAGE_CHARS` (40) are dropped or merged; offsets satisfy `text[start:end] == passage_text`.

```python
def test_split_preserves_offsets_and_drops_tiny():
    src = "Para one is long enough to keep as a passage here.\n\nx\n\nPara two also long enough to keep."
    parts = split_into_passages(src)
    assert all(src[s:e] == t for s, e, t in parts)
    assert all(len(t) >= 40 for _, _, t in parts)
    assert len(parts) == 2
```

- [ ] Step 2: run → FAIL.
- [ ] Step 3: implement — split on `\n\s*\n`, track running offset, strip, keep `len >= _MIN_PASSAGE_CHARS`; `char_start`/`char_end` are offsets of the stripped text within `src` (use `src.index` from the running cursor to stay exact).
- [ ] Step 4: run → PASS. Step 5: commit `feat(ingest): document text passage splitter`.

### Task 3: Passage backfill (text-only + optional embeddings)

**Files:** Modify `ingest/passages.py`; Create `tests/test_passages_backfill.py`.

**Interfaces:** Produces `backfill_passages(pool, *, embed: bool = False, only_missing: bool = True, limit: int | None = None) -> dict[str, int]` (counts: documents, passages).

- [ ] Step 1 (test): seed a case + document with multi-paragraph `text`, run `backfill_passages(pool, embed=False)`, assert `document_passage` rows created with correct `content_hash` and offsets; re-run is idempotent (no dupes). Clean up.
- [ ] Step 2: FAIL. Step 3: implement — select documents with `text IS NOT NULL` and (if `only_missing`) no passages; for each, `split_into_passages`, insert rows (`content_hash = sha256(text)`). When `embed=True`, batch-encode with sentence-transformers and set `embedding`. Resumable. Step 4: PASS. Step 5: commit `feat(ingest): backfill document passages`.
- [ ] Step 6 (operational, not CI): document the prod run — `uv run python -m ingest.passages --embed` over the 64k-doc corpus (hours; resumable). Lexical search works after the text-only pass; embeddings enable semantic.

### Task 4: `find_relevant_passage` tool

**Files:** Create `server/tools/passages.py`; Modify `server/main.py`; Create `tests/test_passages_tool.py`.

**Interfaces:** `find_relevant_passage(case_id_or_sabin_id, claim, top_k=5, semantic=True) -> dict` →
`{case_id, claim, count, matches: [{document_id, para_index, text, highlighted_snippet, char_start, char_end, confidence, source, citation_string}]}` or `{no_match: true, hint: "no passage clearly matches — do not guess a pinpoint"}`.

- [ ] Step 1 (test): seed a case + document + passages (text-only); a claim whose wording matches one passage returns that passage as `matches[0]` with verbatim `text`; an unrelated claim returns `no_match: true`. Clean up. (`semantic=False` to avoid model load in CI.)
- [ ] Step 2: FAIL. Step 3: implement — per-case two-pass FTS (`ts_rank` phrase then OR) over `document_passage` joined to the case; optional semantic cosine when `semantic` and embeddings present; confidence gate = rank gap × token coverage (strip stopwords) with a floor; below floor → `no_match`. `highlighted_snippet` via `ts_headline`. Attach the case `citation_string`. Step 4: PASS.
- [ ] Step 5: register `find_relevant_passage` in `server/main.py` with a description emphasising it returns verbatim, pinpoint-citable passages and refuses to guess. Step 6: commit `feat(mcp): find_relevant_passage — pinpoint a claim to a verbatim passage`.

### Task 5: `get_passage` tool

**Files:** Modify `server/tools/passages.py`, `server/main.py`, `tests/test_passages_tool.py`.

**Interfaces:** `get_passage(document_id, para_index) -> dict | None` → `{document_id, case_id, para_index, char_start, char_end, text, prev_index, next_index, citation_string}`.

- [ ] Step 1 (test): seed passages; `get_passage` returns verbatim text + neighbour indices; not-found → None. Step 2: FAIL. Step 3: implement. Step 4: PASS. Step 5: register + commit `feat(mcp): get_passage — verbatim passage by (document, index)`.

### Task 6: Wire passages into grounding (optional, fast-follow)

- [ ] Extend `attest_response` rail 2 to also match quotes against a retrieved case's `document_passage` text (bounded query: only passages of retrieved cases, via a single FTS/`= ANY` query — not a full-text concat). Update R2 to mention passage-level pinpoint. Tests for a passage-verbatim quote passing and a fabricated one flagging.

### Task 7: Citation-recognizer for climate cites (deferred from plan-04 #1)

- [ ] Add a `case_name` rail to `attest_response` (extract `X v. Y`, match by token-subset against retrieved `canonical_title`, skip names inside verified quotes) so the contract fires on Sabin-style citations — see plan-04 Track A note. Independent of passages; can be done any time.

---

## Self-Review

- Covers the user's requirement — *retrieve case text + precise quotes + citations*: `get_document_text` (shipped in plan-04 follow-on) gives whole-decision text + citation; `find_relevant_passage` / `get_passage` (this plan) give the *precise* passage + pinpoint + citation; `check_claim_support(document_text)` verifies.
- Lexical path works without embeddings → functional immediately after a text-only backfill; semantic is additive.
- Refuse-to-guess gate matches opencaselaw `find_relevant_erwaegung`.
- No placeholders in Tasks 1–5; Tasks 6–7 are flagged fast-follows.
