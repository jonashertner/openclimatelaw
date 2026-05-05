# OpenClimateLaw MCP — Design Specification

- **Date:** 2026-05-05
- **Status:** Draft, awaiting user review
- **Author:** Jonas Hertner (with Claude)
- **Domain:** `openclimatelaw.org` (frontend), `mcp.openclimatelaw.org` (MCP server)
- **Sister project:** `mcp.opencaselaw.ch` (Swiss legal MCP, same author)

## 1. Project overview

A public, hosted Model Context Protocol server that makes the world's climate litigation and climate-law corpus available to AI agents and research tooling. The Sabin Center's Climate Litigation Database is the centerpiece (4,840 cases, 15,000+ documents). The LSE Grantham Climate Change Laws of the World database (1,343+ statutes/policies) is the bridge into legislation. Four further databases — Climate and Human Rights Litigation Database, C2LI, Melbourne's Australian and Pacific Climate Change Litigation Database, and Redline — provide enrichment perspectives and net-new cases.

The MCP enforces an anti-hallucination contract (R1–R5, adapted from `mcp.opencaselaw.ch`) so that downstream LLMs producing legal-research output cannot fabricate citations, quotations, statute text, legislative intent, or case outcomes.

The project is built with the explicit ambition of collaboration with the Sabin Center for Climate Change Law and Climate Policy Radar. The MVP (v0.1) is the demo we use to open that conversation.

## 2. Strategic positioning

**Sabin-centerpiece, not Sabin-equivalent.** The Sabin Center has spent 15+ years building the canonical case database. Climate Policy Radar provides the modern ML/NLP infrastructure (relaunched September 2025). Our role is complementary: an AI-agent-shaped surface over that work, with the same data hygiene discipline.

We adopt Sabin's taxonomies (claim types, jurisdiction codes, document categories, status/outcome enums) verbatim. Where we extend (cross-database deduplication, satellite-perspective enrichment, multilingual matching), we do so as documented additions, not reinventions.

The frontend at `openclimatelaw.org` is a single landing page — pitch, tools list, live stats, prominent credit to Sabin/LSE/CPR, contact. We deliberately avoid building a browse UI that would compete with `climatecasechart.com`.

## 3. Goals and non-goals

### Goals (v0.1)

- Mirror the full Sabin corpus locally with full-text PDFs, Sabin's structured fields, embeddings, and English machine translations of non-English originals.
- Mirror CCLW with statute↔case bridges populated from Sabin's existing references.
- Expose 13 MCP tools covering search, retrieval, citation lookup, statistics, and the anti-hallucination attestation pair.
- Enforce R1–R5 server-side: every case/document/statute reference returned by any tool includes a verbatim `citation_string_*` field.
- Deploy at `mcp.openclimatelaw.org` with the same Streamable-HTTP/SSE shape as `mcp.opencaselaw.ch`.
- Ship a one-page Astro landing at `openclimatelaw.org`.

### Goals (post-v0.1, in roadmap)

- v0.2: Satellite database ingestion + cross-database deduplication.
- v0.3: Augmented citation graph beyond what CPR provides; analytics tools (`compare_jurisdictions`, `analyze_outcome_trends`, `find_landmark_cases`).
- v1.0: After collaboration discussions, possibly migrate to direct Sabin/CPR data feeds; co-branded surface.

### Non-goals

- **A browse-and-read web UI.** That competes with `climatecasechart.com`.
- **A primary-source case repository.** We mirror; we don't host court filings as the upstream of record.
- **Authenticated access / per-user accounts at v0.1.** Public read-only MCP, like opencaselaw.
- **Original case analysis or commentary.** We surface what's in the upstreams. Editorial layers are out of scope.
- **Real-time updates.** Daily refresh is the target cadence; not minute-by-minute.

## 4. Architecture

### 4.1 Data tiers

| Tier | Sources | Coverage | Depth |
|---|---|---|---|
| **Spine** | Sabin Climate Litigation Database | All ~4,840 cases, ~15,000 documents | L4: full text, structured fields, embeddings, citation graph (from CPR) |
| **Bridge** | LSE Grantham CCLW | All ~1,343 statutes/policies | L3: full text, structured fields, statute↔case bridge |
| **Satellites** | Climate Rights DB, C2LI, Melbourne, Redline | Full ingestion (v0.2) | L2: metadata + structured fields + summaries; full text where freely available |

Spine and Bridge share the same upstream (Climate Policy Radar). Satellites have heterogeneous access patterns (a mix of public APIs, scrapable HTML, and database exports).

### 4.2 Stack

- **Server:** FastMCP (Python 3.14, uv) — same toolchain as the existing `at1-mcp-server`.
- **Database:** PostgreSQL 16 + pgvector for embeddings + native FTS (tsvector) for keyword search.
- **Object storage:** Cloudflare R2 (or Backblaze B2) for PDF originals.
- **Embeddings:** Use Climate Policy Radar's pre-computed embeddings if collaboration grants access; fall back to local computation with a documented model (likely `BAAI/bge-m3` for multilingual support).
- **Translation:** NLLB-200 or Claude Sonnet for non-English originals → English; cached per document version. Originals always preserved verbatim.
- **PDF extraction:** `pymupdf` (already in stack from `at1-mcp-server`); fallback to OCR via `tesseract` for scanned briefs.
- **Hosting:** Same infrastructure pattern as `mcp.opencaselaw.ch`. Streamable-HTTP MCP at root, SSE responses.
- **Observability:** structured logs to stdout; Postgres slow-query log; OpenTelemetry to a hosted backend (likely Honeycomb or Grafana Cloud).

### 4.3 Repository layout

```
openclimatelaw/
├── server/                    # FastMCP server
│   ├── tools/                 # One module per tool
│   ├── contracts/             # R1–R5 implementation, citation_string canonicalization
│   ├── db.py                  # Postgres connection + helpers
│   └── main.py                # FastMCP app
├── ingest/                    # Ingestion pipelines (one per source)
│   ├── sabin/
│   ├── cclw/
│   ├── climate_rights/        # v0.2
│   ├── c2li/                  # v0.2
│   ├── melbourne/             # v0.2
│   └── redline/               # v0.2
├── dedup/                     # Cross-database deduplication
├── translate/                 # MT pipeline + cache
├── embed/                     # Embedding pipeline
├── schema/                    # SQL migrations (sqlx-style, numbered)
├── site/                      # Astro v5 landing page (one route)
├── ops/                       # Deployment, Docker, GH Actions
├── docs/
│   └── superpowers/specs/     # This spec lives here
├── pyproject.toml
└── README.md
```

Mirrors the boundaries of `agents/`, `site/`, `scripts/` from the open-legal-commentary project.

## 5. Data model

PostgreSQL schema. Field-level provenance is a first-class concern — every populated field tracks which source, which retrieval timestamp, which upstream version.

### 5.1 Core tables

```
case
  id                  UUID PK
  sabin_id            TEXT UNIQUE NULL    -- Sabin's case ID, when present
  canonical_title     TEXT NOT NULL
  jurisdiction_iso    TEXT NOT NULL       -- ISO 3166-1 alpha-2 + special codes for international bodies (ICJ, IACTHR, ECTHR, etc.)
  court_id            TEXT NOT NULL       -- Sabin's court vocabulary
  filing_date         DATE NULL
  decision_date       DATE NULL
  status              TEXT NOT NULL       -- Sabin's status enum, sourced verbatim from upstream taxonomy export (see §5.2)
  outcome             TEXT NULL           -- Sabin's outcome enum, sourced verbatim from upstream taxonomy export (see §5.2)
  summary             TEXT NULL
  summary_lang        TEXT NOT NULL DEFAULT 'en'
  primary_source      TEXT NOT NULL       -- 'sabin' | 'climate_rights' | 'c2li' | 'melbourne' | 'redline'
  provenance          JSONB NOT NULL      -- field-level source tags
  created_at          TIMESTAMPTZ NOT NULL
  updated_at          TIMESTAMPTZ NOT NULL

case_party
  case_id             UUID FK
  side                TEXT NOT NULL       -- 'plaintiff' | 'defendant' | 'intervenor' | 'amicus'
  name                TEXT NOT NULL
  party_type          TEXT NULL           -- 'individual' | 'ngo' | 'corporation' | 'state' | 'sub_state'

case_claim_type
  case_id             UUID FK
  claim_type          TEXT NOT NULL       -- Sabin's controlled vocabulary

citation_string
  case_id             UUID FK
  lang                TEXT NOT NULL       -- 'en' | 'de' | 'fr' | 'es' | 'pt' | 'it' | 'nl'
  format              TEXT NOT NULL       -- 'sabin' | 'bluebook' | 'oscola' | 'iclq' | source-native
  text                TEXT NOT NULL
  PRIMARY KEY (case_id, lang, format)

document
  id                  UUID PK
  case_id             UUID FK
  category            TEXT NOT NULL       -- Sabin's document category enum
  title               TEXT NOT NULL
  filed_date          DATE NULL
  filed_by            TEXT NULL
  upstream_url        TEXT NOT NULL
  storage_url         TEXT NULL           -- R2 URL of mirrored PDF
  text                TEXT NULL           -- extracted full text
  text_lang           TEXT NULL
  text_extraction_method  TEXT NULL       -- 'pymupdf' | 'tesseract' | 'upstream_provided'
  text_translation_en TEXT NULL           -- MT to English when text_lang != 'en'
  embedding           VECTOR(1024) NULL   -- bge-m3 or CPR embedding
  provenance          JSONB NOT NULL

statute
  id                  UUID PK
  cclw_id             TEXT UNIQUE
  jurisdiction_iso    TEXT NOT NULL
  short_title         TEXT NOT NULL
  long_title          TEXT NULL
  enacted_date        DATE NULL
  status              TEXT NOT NULL       -- CCLW status enum
  text                TEXT NULL
  text_lang           TEXT NULL
  embedding           VECTOR(1024) NULL
  provenance          JSONB NOT NULL

case_statute
  case_id             UUID FK
  statute_id          UUID FK
  relationship        TEXT NOT NULL       -- 'enforces' | 'challenges' | 'interprets' | 'cited' | 'referenced'
  source_of_link      TEXT NOT NULL       -- 'sabin' | 'inferred_nlp' | etc.

citation_edge
  citing_case_id      UUID FK
  cited_case_id       UUID NULL FK        -- when target is in our DB
  cited_authority     TEXT NULL           -- when target is external (foreign court, statute, treaty)
  citation_string     TEXT NOT NULL       -- as written in the citing document
  span_in_document    JSONB NULL          -- {document_id, char_start, char_end}
  source_of_edge      TEXT NOT NULL       -- 'cpr' | 'sabin_structured' | 'inferred_nlp'

merge_candidate                           -- for dedup human review queue
  case_id_a           UUID FK
  case_id_b           UUID FK
  score               FLOAT NOT NULL
  features            JSONB NOT NULL      -- explainable match features
  status              TEXT NOT NULL       -- 'pending' | 'merged' | 'rejected'
```

### 5.2 Controlled vocabularies

Sourced from Sabin verbatim where possible:

- `jurisdiction` — ISO 3166-1 + non-ISO codes for international bodies (`ICJ`, `IACTHR`, `ECTHR`, `UNHRC`, `ITLOS`, `WTO`, `EU-CJEU`).
- `court` — Sabin's court vocabulary (each `court_id` resolves to `(name, jurisdiction_iso, court_level)`).
- `claim_type` — Sabin's claim-type taxonomy.
- `document_category` — `decision | order | complaint | brief | agency_record | settlement | judgment | dissent`.
- `status` and `outcome` — Sabin's enums.

Stored as separate `vocabulary_*` tables with `source_version` so we can detect upstream taxonomy changes.

### 5.3 Provenance model

The `provenance` JSONB column on `case`, `document`, `statute` records, per field:

```json
{
  "summary": {
    "source": "sabin",
    "retrieved_at": "2026-05-12T14:00:00Z",
    "upstream_version": "cpr-v2.3"
  },
  "outcome": {
    "source": "sabin",
    "retrieved_at": "2026-05-12T14:00:00Z",
    "upstream_version": "cpr-v2.3"
  }
}
```

When satellite data enriches a Sabin record, the `_alt_perspectives` array on the case-level read tools surfaces the alternative values:

```json
{
  "summary": "Sabin's summary text...",
  "_alt_perspectives": {
    "summary": [
      {"source": "climate_rights_db", "text": "Human-rights framing summary..."}
    ]
  }
}
```

## 6. Ingestion pipelines

### 6.1 Sabin (primary)

Three access paths, ordered by preference:

1. **Bulk data export from Sabin/CPR** — pursued as part of the collaboration ask. Replaces all other paths if granted.
2. **CPR's organisation-facing API** — announced but not yet GA as of 2026-05. Once available we move here.
3. **CPR's frontend-serving API** — the JSON endpoints the relaunched `climatecasechart.com` calls from the browser. Discoverable from CPR's open-source frontend repo on GitHub. Used at v0.1 only if (1) and (2) are unavailable, with politeness defaults: 1 req/sec, exponential backoff on 429, full snapshot weekly with daily diff polling, contact email in `User-Agent`.

Whichever path is used, raw upstream responses are mirrored to R2 for replayability when the upstream changes shape.

Pipeline stages:

```
fetch_case_index     → list of all Sabin case IDs + last_modified timestamps
fetch_case_records   → JSON record per case
fetch_documents      → PDF download to R2; extract text with pymupdf (fallback OCR)
translate            → NLLB-200 to English when text_lang != 'en'; cache
embed                → bge-m3 (or CPR-provided) on (text, text_translation_en)
upsert               → idempotent UPSERT keyed on sabin_id
update_citation_graph → from CPR's pre-computed edges
```

Each stage is a separate worker, idempotent, restartable. Run as cron (initially) → eventually a queue (Postgres-backed `pgmq` or NATS).

### 6.2 CCLW

Same upstream (Climate Policy Radar). Same access pattern. Smaller corpus, simpler pipeline. Statute↔case links populated from Sabin's existing structured `cited_statutes` field.

### 6.3 Satellites (v0.2)

Per-source adapter:

- **Climate Rights DB** — public site at `climaterightsdatabase.com`, no documented API. HTML scraper, HTTP politeness, weekly full crawl.
- **C2LI** — `c2li.org`, scenario-by-country structure. Lightweight scraper.
- **Melbourne** — `law.app.unimelb.edu.au/climate-change`. Has a search interface, may be willing to share an export (analogous outreach to Sabin).
- **Redline** — `redlinedatabase.org`, fossil-fuel-accountability focus.

All satellite ingestion ends with a deduplication pass (§7) that merges into the Sabin spine where matches.

### 6.4 Translation pipeline

For each `document.text` where `text_lang != 'en'`:

1. Skip if `text_translation_en` already exists for this document version.
2. NLLB-200 (local, batched) for documents up to 50KB.
3. Claude Sonnet (API) for larger documents or where NLLB quality is insufficient (legal language).
4. Store with `translation_model`, `translation_version`, `translated_at`.
5. Tools clearly mark translated text: every translated string returns alongside the original, with `translation_method` and a "this is a machine translation" flag.

Originals are always preserved verbatim. Per R2 (anti-hallucination contract), machine translations may not be used as authoritative quotations; this is enforced server-side. The `get_document_text` tool returns originals as the canonical text; translations are an `_translation_en` field, and `attest_response` rejects quotations attributed to the original that only match the translation.

### 6.5 Embeddings

- Model: `BAAI/bge-m3` (multilingual, 1024-dim, strong cross-language retrieval). Fallback to CPR's embeddings if granted.
- Indexed in pgvector with HNSW.
- Computed over full document text (chunked at ~512 tokens with overlap; per-chunk embeddings stored; document-level mean-pooled embedding for case-level search).

## 7. Cross-database deduplication

### 7.1 Identity resolution

1. **Strong key:** Sabin case ID, when present in satellite record (most satellites link out to `climatecasechart.com`).
2. **Probabilistic match:** tuple feature `(jurisdiction_iso, court_id, normalized_party_set, filing_year, docket_normalized)`.
   - Party normalization: lowercase, strip honorifics, sort, jaccard against opposing case's party set.
   - Docket normalization: strip leading zeros, normalize separators.
   - Score = weighted sum (jurisdiction 0.2, court 0.2, parties 0.4, year 0.1, docket 0.1).
3. **Decision thresholds:**
   - ≥ 0.85 → auto-merge with provenance trail.
   - 0.6–0.85 → `merge_candidate` row, manual review queue.
   - < 0.6 → no merge.
4. **Net-new from satellites:** record gets a UUID, `primary_source` set accordingly.

### 7.2 Field merge policy

- For overlapping cases, Sabin values win for canonical fields (`status`, `outcome`, `claim_type`, `summary`).
- Satellite values are preserved as `_alt_perspectives` and exposed via `get_satellite_perspective(case_id, source=...)`.
- Conflict surfaces (e.g., Sabin says `decided`, Climate Rights DB says `pending`) trigger a conflict log + Sabin wins by default.

## 8. Anti-hallucination contract (R1–R5)

Server-side enforced. Documented in the MCP server's manifest so client LLMs can read the contract.

- **R1 — Never construct a citation.** Every case reference produced by any tool must be a verbatim `citation_string_*` field returned by an earlier tool call. If a downstream LLM needs a citation it didn't retrieve, it must call `cite(case_id, lang, format)` to get one — and it must already hold a valid case_id, which means it must have searched first. **If a case is not in our database, the LLM must describe the authority in prose without a formal citation.** Constructing a citation from training data is the failure mode this rule exists to prevent. The `attest_response` tool flags any citation-shaped string in a draft that isn't present in retrieved data.
- **R2 — Never quote what wasn't retrieved.** Direct quotations (in quotation marks) must match a substring of `document.text`, `case.summary`, `statute.text`, or `citation_string`. `check_claim_support(quote, source_id)` validates.
- **R3 — Never state statute content from memory.** Tool-side enforcement: `search_legislation` and `get_legislation` are the only paths to statute text.
- **R4 — Never speculate on legislative intent.** UNFCCC negotiating history, Paris Agreement *travaux*, national legislative records exposed via `get_materialien` (v0.3+); until then, intent claims must be retrieved from a case's `summary` (Sabin's editorial framing) or a statute's `summary`.
- **R5 — Never assert outcome/status without retrieval.** `outcome` and `status` are first-class fields; tools never paraphrase them without including the structured value.

## 9. MCP tool surface (v0.1)

Thirteen tools.

| Tool | Purpose |
|---|---|
| `search_cases(query, jurisdiction?, claim_type?, status?, date_range?, limit?)` | Hybrid keyword + semantic search across Sabin corpus. Returns case headers + `citation_string_en` for each hit. |
| `get_case(case_id)` | Full case record: parties, claim types, status, outcome, summary, document index, citation strings in all available languages. |
| `get_case_documents(case_id, category?)` | Document index for a case. Each entry includes upstream URL + storage URL (if mirrored) + extraction method + language. |
| `get_document_text(document_id, include_translation?)` | Full text of a document. Returns original; `include_translation=true` adds English MT in `_translation_en`. |
| `find_citations(case_id)` | Cases this case cites (forward edges). |
| `find_cited_by(case_id)` | Cases that cite this case (backward edges). |
| `search_legislation(query, jurisdiction?, status?)` | Hybrid keyword + semantic search across CCLW. |
| `get_legislation(statute_id)` | Full statute record + text. |
| `find_cases_for_statute(statute_id, relationship?)` | Cases linked to a statute via `case_statute`. |
| `get_statistics(scope, group_by?)` | Aggregations: cases per jurisdiction per year, claim-type distributions, outcome rates. Returns structured tables, not prose. |
| `cite(case_id, lang, format)` | Returns the canonical `citation_string` for a case in the requested language and format. Requires a valid `case_id` (not a name or descriptor) — preventing R1 violation by construction. If the caller has only a name, they must `search_cases` first. |
| `attest_response(draft_text, retrieved_ids[])` | Validates a draft response. Substring-matches `draft_text` against the union of `citation_string_*` values from records in `retrieved_ids`; flags any contiguous run that pattern-matches a known citation format (Bluebook/OSCOLA/Sabin/ICJ/etc., per registered regexes) but is absent from that union. Returns `{passed: bool, violations: [{span, text, reason}], suggested_replacements?}`. |
| `check_claim_support(quote, source_id)` | Validates that a direct quotation appears verbatim in the named source's text. |

Each tool returns structured JSON with `citation_string_*` fields populated for every case/document/statute reference. No tool returns free prose without a structured payload.

## 10. Frontend (v0.1)

Single Astro v5 page at `openclimatelaw.org`. Reuses the toolchain from `open-legal-commentary` and `open-gov-climate`.

Sections:

1. **Pitch** — one-paragraph framing. "An MCP server that makes the world's climate litigation corpus available to AI agents and research tools, with anti-hallucination guarantees."
2. **Live stats** — case count, document count, jurisdictions, last refresh timestamp. Pulled from `get_statistics` at build time + via a daily CI job.
3. **Tools** — list of the 13 tools with one-line descriptions.
4. **Credits** — Sabin Center, LSE Grantham, Climate Policy Radar, named prominently with links to upstream sites. Explicit statement: "Built on data from these sources. This project does not replace them; it provides an alternative access surface."
5. **Connect to Claude / agents** — copy-paste MCP URL + setup snippet.
6. **Status / changelog** — version history, known issues.
7. **Contact** — email + GitHub link.

No browse UI. No search. Anyone wanting to browse goes to `climatecasechart.com`.

## 11. Hosting and deployment

- **MCP server** — single-process FastMCP behind a reverse proxy. Streamable-HTTP at `/`, SSE responses. TLS via Let's Encrypt.
- **Postgres** — managed (Neon, Supabase, or self-hosted on the same box). pgvector + tsvector. Daily backups to R2.
- **R2** — PDFs + translation cache + embeddings cache.
- **Frontend** — built by GitHub Actions, deployed to GitHub Pages or Cloudflare Pages.
- **Domain** — `openclimatelaw.org` (apex → frontend), `mcp.openclimatelaw.org` (MCP server). DNS via Cloudflare.
- **Logs** — structured stdout, shipped to a hosted log backend.
- **Health** — `/health` endpoint, monitored by Uptime Kuma or similar.
- **No auth** at v0.1. Rate limit: 60 req/min per IP, 1000/hr.
- **Storage budget at v0.1:** Postgres ≈ 5–10 GB (case + document + statute + edge tables); pgvector index ≈ 30–50 GB (15,000 documents × ~500 chunks/doc × 1024-dim float32 + HNSW overhead); R2 PDFs ≈ 30–80 GB; translation cache ≈ 5 GB. Provision 200 GB headroom.

## 12. Outreach plan

Once v0.1 is deployed and demonstrably stable (≥1 week uptime, all tools functional), send one coordinated email:

- **Recipients:** Michael Burger (Sabin Executive Director), Maria Antonia Tigre (Climate Litigation Network), CPR technical leadership.
- **Subject:** "OpenClimateLaw MCP — proposed collaboration"
- **Content:** Single page. (1) what we built and why; (2) live demo URL with sample queries; (3) explicit acknowledgement that Sabin is the centerpiece and CPR provides the infrastructure; (4) what we'd ask for: bulk data export, schema documentation, embeddings access, update mechanism, posture on co-branding, redistribution licence clarity; (5) what we'd offer back: maintained MCP surface, contributed taxonomy extensions, traffic referral, anti-hallucination tooling that may be useful for their own LLM partnerships.

Critical-path discipline: the outreach email is a deliverable in v0.1, not a research task in week 0.

## 13. Phased roadmap

| Phase | Duration | Deliverables | Success criterion |
|---|---|---|---|
| **v0.1 — Sabin core + CCLW + landing + outreach** | 8 weeks | Sabin ingestion (incl. PDF download, OCR fallback, MT, embeddings), CCLW ingestion, 13 tools, anti-hallucination contract, Astro landing, deployed at production domain, outreach email sent | All ~4,840 Sabin cases queryable; sample LLM session produces a research note that passes `attest_response` |
| **v0.2 — Satellites + dedup** | 6 weeks | All 4 satellite ingestions, dedup pipeline, `get_satellite_perspective` tool | ≥80% of satellite cases either merged with Sabin or net-new with full records |
| **v0.3 — Citation graph + analytics** | 8 weeks | NLP citation extraction beyond CPR, `compare_jurisdictions`, `analyze_outcome_trends`, `find_landmark_cases`, `get_materialien` (Paris Agreement *travaux*, UNFCCC) | Citation graph density ≥1.5× CPR baseline; analytics tools answer 5 sample research questions correctly |
| **v1.0 — Post-collaboration consolidation** | After Sabin/CPR conversations conclude | Whatever the collaboration unlocks: direct data feeds, co-branding, schema co-evolution | Sabin/CPR endorse or co-list the project, OR we have a clear independent path with explicit licence terms |

## 14. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CPR API changes break ingestion | Medium | High | Pin to a documented API version; CI integration test against staging endpoint; mirror raw API responses to R2 for replay |
| Sabin/CPR object to the project | Low–Medium | High | Outreach early; respect their taxonomy; explicit credit; offer to discontinue if they prefer; design for graceful shutdown if asked |
| Bulk redistribution licence unclear for some sources | High | High | **Verification action before any v0.1 ingestion runs:** read Sabin's published terms of use on `climatecasechart.com` and CCLW's terms on `climate-laws.org`; document the licence governing redistribution of (a) metadata, (b) summaries authored by Sabin, (c) court-document text. If terms forbid mirroring, switch to live-proxy for affected fields, or contact Sabin/CPR for explicit permission as part of the outreach (this is a pre-launch gate, not a post-launch concern). Defer satellites until each licence is similarly confirmed. |
| Scrape fragility on satellite sources | High | Low | Per-source error budgets; failing satellite degrades gracefully (its data simply absent), doesn't break Sabin spine |
| Embedding quality insufficient for cross-language retrieval | Medium | Medium | Evaluate bge-m3 against a held-out set of multilingual climate cases before locking in |
| Abuse (scrape-our-mirror) | Medium | Low | Rate limits + standard MCP polite headers + monitoring |
| Outdated taxonomies as Sabin evolves | Medium | Medium | Track `vocabulary_*.source_version`; daily diff alert; manual review and re-ingest on change |
| Cost escalation (storage, compute, MT) | Medium | Medium | Budget targets per phase; alarm if monthly cost > $200 in v0.1 |

## 15. Open questions

To resolve before implementation begins (writing-plans phase):

- **Q-OPEN-1:** Hosting target — same VPS/cloud as `mcp.opencaselaw.ch`, or new? (Affects ops parallelism and cost accounting.)
- **Q-OPEN-2:** Postgres — managed (Neon/Supabase) vs self-hosted on the MCP box? (Affects backup story and cost.)
- **Q-OPEN-3:** Translation model — NLLB-200 default with Claude Sonnet escalation, or Claude Sonnet for everything? (Quality vs cost trade.)
- **Q-OPEN-4:** Embeddings model — confirm `BAAI/bge-m3` with a small evaluation set before locking in.
- **Q-OPEN-5:** Frontend repo — separate (`openclimatelaw-site`) or in the monorepo at `site/`? Defaulting to monorepo `site/` per the open-legal-commentary precedent.
- **Q-OPEN-6:** Confirm Sabin's published licence allows the planned redistribution. (Public-facing answer needed before launch.)
- **Q-OPEN-7:** Should `attest_response` be opinionated (refuses on any violation) or graded (returns a confidence score)? Default: opinionated, with `strict=false` for grading.

## 16. Glossary

- **MCP** — Model Context Protocol. A standard for exposing tools and resources to LLMs.
- **Sabin Center** — The Sabin Center for Climate Change Law at Columbia Law School; maintainer of the Climate Litigation Database.
- **CCLW** — Climate Change Laws of the World, maintained by the LSE Grantham Research Institute.
- **CPR** — Climate Policy Radar, the technical infrastructure provider behind the relaunched Sabin database and CCLW.
- **R1–R5** — The five anti-hallucination rules adopted from `mcp.opencaselaw.ch`.
- **Spine / Bridge / Satellites** — Project's tier model. Spine = Sabin; Bridge = CCLW; Satellites = the four other case databases.
