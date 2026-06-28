# Demo Runbook — Sabin Center + Climate Policy Radar

> Audience: the two orgs that **jointly relaunched** the Climate Litigation Database (25 Sept 2025,
> CPR-powered). They are partners, not prospects. Frame OpenClimateLaw as the **citation-safe
> MCP/agent layer on top of their official data**, not a competing database.
> **Dry-run every query the morning of.** All IDs/outputs below were verified on prod 2026-06-28.

## Opening frame (60s)
- LLMs are already answering climate-law questions against *your* data — and hallucinating citations
  and holdings (Stanford/Magesh 2025: even RAG-grounded Lexis+/Westlaw hallucinate 17–33%).
- OpenClimateLaw is an **open-source MCP server** that gives an LLM a *citation-safe* interface to
  this corpus: every citation verbatim from the data, every quote verified, **refuses to guess**.
- Philosophy: **verifiability > veracity** — an unverifiable answer can't be checked; a verifiable one
  always can.

## Beat 1 — The fabrication catch (the headline) ~2 min
Show a normal LLM inventing a plausible cite, then run the same draft through `attest_response`:
- Tool: `attest_response(draft_text, retrieved_ids=["Sabin.family.2823.0"])`
- Draft (planted fakes): *"As held in Smith v. Exxon Global, 999 U.S. 1 (2030), and ECLI:NL:HR:2099:9999, emitters owe a duty."*
- **Verified result:** `passed=false`, violations flag `999 U.S. 1` and `ECLI:NL:HR:2099:9999`.
- Line: "It cannot pass a draft that cites something not in your database."

## Beat 2 — Grounded verbatim research ~4 min
1. `search_cases("Massachusetts EPA greenhouse gas")` → `Sabin.family.151.0` (verified clean, no duplicates).
2. `get_document_text(<doc>)` → verbatim opinion text, paginated (100k+ char rulings supported).
3. `find_relevant_passage(Sabin.family.151.0, "EPA has statutory authority to regulate greenhouse gases as air pollutants")` → **verified count=4, confidence 1.0, a verbatim passage**.
4. `check_claim_support(<that exact quote>, source_kind="document_text")` → **verified `supported=true`**.
5. **Refuse-to-guess beat:** ask `find_relevant_passage` a claim no passage supports → `{no_match:true, hint:"do not guess a pinpoint"}`. "It would rather say nothing than invent."

## Beat 3 — Cross-jurisdiction discovery ~2 min
- `find_related_cases("Sabin.family.2823.0")` (Urgenda) → **verified**: Greenpeace NL, German youth
  constitutional cases (Luca Salis / Leonie Frank), Plan B.Earth v UK — by *embedding similarity*, not
  keywords. "Analogues across jurisdictions a keyword search misses."

## Beat 4 — Honesty / provenance ~1 min
- `get_case("Sabin.family.2823.0")` → field-level provenance (`source: sabin`, `retrieved_at`), and a
  `citation_string` that links back to climatecasechart.com — never constructed by the model.
- Say the as-of date out loud (currently `2026-05-07`) and our pinned-provenance posture.
- Hand over the one-page **Data-Quality QA report** (docs/demo/data-quality-report.md) as a gift.

## Beat 5 — The asks ~2 min
- **Sabin:** bless a citation-safe MCP layer over your *official* data; accept the QA report; confirm
  the litigation-corpus license/attribution terms.
- **CPR:** ingest CCLW to add the missing statute layer and cross-link litigation ↔ legislation; adopt
  your `import_id` as our dedup key and your concept annotations; treat this as the agent-distribution
  layer for your open corpus.

## DO NOT demo (known-fragile)
- `sort="newest"` discussion beyond "real Decision-event dates now" — fine to show, but don't dwell.
- `find_citations` / `find_cited_by` on flagships — the citation graph is thin.
- `find_relevant_passage` on **foreign-language** cases (e.g. Urgenda's Dutch ruling) → returns
  `no_match` (English claim can't match Dutch text). Use English-language cases for pinpoint.
- Typing **KlimaSeniorinnen** or the **2025 ICJ Advisory Opinion** cold — not yet present as canonical
  records (only CRD blog stubs). If asked, name it as roadmap (re-ingest from the official channel).

## Pre-demo checklist
- [ ] Re-run each beat's exact query live the morning of; capture fresh IDs.
- [ ] `curl https://mcp.openclimatelaw.org/health` returns ok.
- [ ] Confirm `search "Urgenda"` shows the NL Sabin record at #1 with no `crd:` stubs.
- [ ] Have screenshots of every beat as an offline fallback.
