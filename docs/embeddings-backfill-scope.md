# Embeddings-at-scale backfill — scope

> Prepared 2026-07-01. Goal: make `find_relevant_passage` (semantic pinpoint) actually work,
> across languages. Driven by a real production failure (below).

## Why now
Semantic pinpoint is effectively dead: **3,000 of 4,981,454 passages are embedded (0.06%)**. On
2026-07-01 the first serious user (via claude.ai) researched the ICJ Advisory Opinion and got
`no_match` on 2 of 3 cases — the target decisions were in **Portuguese and Japanese**. They ran
`find_relevant_passage` 7 times, rephrasing English→Portuguese, before giving up. The
`no_match` rate is now instrumented in the usage QC report, so this is measurable.

## Measured facts (prod, 2026-07-01)
| | |
|---|---|
| Passages | **4,981,454** total · **3,000** embedded · avg 1,051 chars (p50 412, p95 3,594, max 69,418) |
| **Dedup** | **1,098,919 distinct `content_hash` (22% unique → 78% duplicate)** |
| **Multilingual** | **55% of passages contain non-ASCII text** (accented / CJK) |
| Model today | `all-MiniLM-L6-v2` (384-dim, English-centric); 256-token window |
| pgvector | 0.8.2 (**`halfvec` available** → 2 bytes/dim) |
| Index | an HNSW index on `document_passage.embedding` exists (≈empty) |
| VPS | 2 vCPU · ~4 GB RAM (~2.4 GB free) · 75 GB disk (37 GB free); Postgres 10 GB, passages table 6.7 GB |
| Query shape | `find_relevant_passage` is **per-case** — a global ANN index is NOT required for correctness |

## The two facts that make this tractable
1. **78% duplicates** → embed **~1.1M distinct** passages, propagate by `content_hash`. 4.5× less
   compute and storage than the naive 5M.
2. **Per-case search** → for a single case (tens–hundreds of passages) a brute-force cosine is
   trivially fast; no giant resident HNSW index needed. Removes the VPS-RAM concern. (A global
   semantic-search tool, if ever added, would build HNSW on the 1.1M dedup set then.)

## Phase 0 result (2026-07-01) — model VALIDATED on the real failure
A/B on the *Climate Justice Case* (JP), which genuinely cites the ICJ AO (passages 64/65/153/164,
Japanese), with the user's English claim. Current `all-MiniLM-L6-v2` ranked the gold passages
**36 / 20 / 114 / 105** at cosine **~0.1–0.2** (→ guaranteed `no_match`). `multilingual-e5-small`
ranked them **2 / 4 / 5 / 12**, all **≥0.80**, 3 in the top-5. Root cause is the **model**, not data
absence. **Decision: adopt `intfloat/multilingual-e5-small` (384-dim, drop-in).**

## Recommended approach
- **Model — multilingual, same dimension.** **`multilingual-e5-small`** (384-dim, validated above).
  Use a **dedicated passage embedder** (same model for the passage-claim query); leave case-search
  embeddings on the current model to isolate blast radius. Two impl notes: e5 needs `query:` /
  `passage:` prefixes, and its cosine distribution runs high — **re-calibrate `find_relevant_passage`'s
  confidence / `no_match` threshold** for it. *(Alternative: a hosted multilingual embedding API —
  simpler ops, external per-query dependency for a citation-safe tool. Lean self-hosted.)*
- **Storage — dedup table.** `passage_embedding(content_hash PK, embedding halfvec(384))`, ~1.1M
  rows ≈ **~0.85 GB**; `document_passage` joins by `content_hash`. (Or `halfvec` directly on
  `document_passage.embedding` if we prefer no query change — ~3.8 GB, still fine on disk.)
- **Compute — off-VPS, one-time.** Stream the 1.1M distinct passage texts out → embed on a rented
  GPU (~15–20 min, **< $5**) or a strong CPU box → bulk-`COPY` vectors in. Never grind on the live
  2-vCPU VPS (OOM + latency risk for live users).
- **Chunking caveat.** p95 passage ≈ 3,594 chars (~900 tokens) exceeds the model's 256-token
  window, so v1 embeds the head only. Ship v1, measure, then v2 sub-chunks to ~256 tokens for
  higher recall.
- **Ongoing.** Wire embed-on-ingest so new passages are embedded (small volume) with the same model.

## Phases (~3 days engineering)
0. **Model pick (½ d).** A/B `MiniLM` vs multilingual on the *known-failing* cases (Climate Justice
   Case JP, Tenharim BR, English claims). Prove the win before scaling.
1. **Dedup embed job (1 d).** Stream distinct `content_hash` → embed off-VPS → vectors file.
2. **Load + wire (½ d).** `halfvec` column / dedup table; bulk-load; point `find_relevant_passage`
   at the multilingual query embedder (+ the join, if dedup table).
3. **Ongoing + validate (½ d).** embed-on-ingest; re-run the failing queries; watch the live QC
   `no_match` rate fall.

## Cost / footprint
- One-time compute: **< $20** (GPU rental or embedding API).
- Storage: **+~1–4 GB** Postgres (fits the current 37 GB free).
- VPS: **likely no upgrade** (dedup + per-case search). Revisit only if a global ANN tool is added.
- Ongoing: negligible.

## Acceptance metric
`find_relevant_passage` `no_match` rate (already in the usage QC report) drops from majority to low,
and the failing user's exact queries return grounded passages. Measured on live traffic.

## Decision points
1. **Multilingual model swap** — confirm direction (fixes 55% of the corpus).
2. **Self-hosted model vs hosted embedding API** — ops simplicity + per-query latency vs an external
   dependency in a citation-safe tool.
3. **Chunking** — ship v1 (head-only) first, then v2 sub-chunking? (Recommended.)
4. **Full 1.1M vs a subset** — full is cheap now; no reason to subset.
