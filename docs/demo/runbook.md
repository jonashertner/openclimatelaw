# Demo Runbook — Sabin Center + Climate Policy Radar

> **Audience:** the two organisations that **jointly relaunched** the Climate Litigation Database
> (25 Sept 2025, CPR-powered). They are **partners, not prospects.** Frame OpenClimateLaw as the
> **citation-safe MCP / agent layer on top of their official data** — never a competing database.
>
> **All beats below were dry-run on prod and verified on 2026-06-29.** Re-run them the morning of
> (IDs can shift — see "duplicate records" under DO NOT DEMO). Corpus as-of: **2026-05-07**.
>
> **Shape:** ~16 min of beats + Q&A. Endpoint: `https://mcp.openclimatelaw.org/mcp`.

---

## Pre-demo checklist (do these first)

- [ ] **Decide on the grounding-judge beat.** `verify_grounding` (the fabricated-*holding* catch,
      Beat 1b) is **dormant in prod** until an Anthropic key is set in `deploy/.env.production`.
      To show it: rotate the key, add it to `.env.production`, redeploy, confirm
      `verify_grounding(... )` returns `available: true`. If you skip this, drop Beat 1b and show
      only the deterministic citation/quote rails (still strong).
- [ ] **Dry-run every beat live**, capturing fresh IDs. Flagships have duplicate family records;
      pull them by the pinned IDs below and confirm each resolves.
- [ ] `curl -s https://mcp.openclimatelaw.org/health` → `{"status":"ok"}`.
- [ ] **Screenshot every beat** as an offline fallback (network/proxy can blip).
- [ ] Have the one-page **Data-Quality QA report** (`docs/demo/data-quality-report.md`) printed to
      hand over in Beat 6.

---

## Opening frame (60s)

- LLMs are already answering climate-law questions against *your* data — and **fabricating citations
  and holdings.** Even RAG-grounded Lexis+/Westlaw hallucinate **17–33%** (Stanford / Magesh 2025).
- OpenClimateLaw is an **open-source MCP server** that gives any LLM (Claude, ChatGPT, Gemini,
  Copilot, …) a **citation-safe** interface to this corpus — now spanning **both halves of the field:
  litigation (your database) and legislation (CPR's CCLW)**.
- The contract: **every citation verbatim from the data, every quote verified, refuses to guess.**
  Philosophy — **verifiability > veracity:** an unverifiable answer can't be checked; a verifiable
  one always can.
- Scale, in one line: **5,027 cases · 5,347 climate laws · 81,345 court documents · 16 tools.**

---

## Beat 1 — The fabrication catch (the headline) · ~2.5 min

Show a normal LLM inventing plausible cites, then run the same draft through `attest_response`.

- **Tool:** `attest_response(draft_text, retrieved_ids=["Sabin.family.2823.0"])`
- **Draft (planted fakes):** *"As held in Smith v. Exxon, 999 U.S. 1 (2030) and Plan B v PM
  [2099] EWHC 9999 (Admin), emitters owe a duty."*
- **Verified result:** `passed=false`, **2 violations** — the US reporter **and the UK neutral
  citation**. Line: *"It cannot pass a draft that cites something not in your database — and now it
  reads citations from every major system: US reporters, ECLI, UK, Australia/NZ, Canada, Ireland,
  South Africa, India, the CJEU."*

**Beat 1b — the fabricated *holding* catch (only if `verify_grounding` is activated):**
- **Tool:** `verify_grounding("In Urgenda, the court ordered every citizen to receive €5bn.",
  ["Sabin.family.2823.0"])`
- **Verified result:** `supported=false`, flagged `holding_not_supported` — and a fabricated case
  *name* ("Smith v. United Kingdom (2019) held …") flags `case_not_in_sources`. Line: *"A semantic
  judge catches the fabrications regex can't — invented holdings and invented case names."*

---

## Beat 2 — Grounded verbatim research · ~4 min

The core loop: find → read → pinpoint → verify → cite. **Use an English-language US case** (pinpoint
is reliable there).

1. `search_cases("EPA greenhouse gas regulation authority", jurisdiction="US")`, or retrieve
   **`Sabin.family.151.0`** directly (*Energy-Intensive Manufacturers Working Group on GHG
   Regulation v. EPA*). Don't announce a case name before it's on screen.
2. `get_document_text(<doc>)` → verbatim opinion text, paginated (100k+ char rulings handled).
3. `find_relevant_passage("Sabin.family.151.0", "EPA has statutory authority to regulate greenhouse
   gases as air pollutants")` → **a verbatim passage, confidence 1.0, with its citation_string.**
4. `check_claim_support(<that exact quote>, source_id=<document_id>, source_kind="document_text")`
   → **`supported=true`** (whitespace/quote-normalised, so a normally-pasted quote verifies).
5. **Refuse-to-guess beat:** ask `find_relevant_passage` a claim no passage supports →
   `{no_match:true, hint:"do not guess a pinpoint"}`. *"It would rather say nothing than invent."*

---

## Beat 3 — Litigation ↔ legislation: the joint payoff · ~3 min  ⟵ *the Sabin + CPR moment*

The thing neither database does alone — connect a case to the **actual law it turns on**, with the
verbatim statute text.

- **The legislation corpus is live:** `search_statutes("renewable energy targets")` → **1,765 laws
  across ~200 jurisdictions** (China's 14th Five-Year Plan, the EU 2020 Climate & Energy Package, …),
  full multilingual text via `get_statute`.
- **The bridge:** `get_case("Sabin.family.7481.0")` (*Friends of the Earth and Others v. Secretary of
  State*, GB) → **`linked_statutes` → Climate Change Act 2008** (`CCLW.family.1755.0`) → `get_statute`
  → the **verbatim Act text**. A climate case → its parties → the law it references → the law itself.
- **The reverse:** `find_cases_by_law("European Convention on Human Rights")` → **60 cases across
  jurisdictions** (KlimaSeniorinnen, Urgenda lineage). Line: *"Your litigation, CPR's legislation,
  one grounded path — this is what the partnership unlocks."*

---

## Beat 4 — Cross-jurisdiction discovery · ~2 min

- `find_related_cases("Sabin.family.2823.0")` (Urgenda) → **Greenpeace Netherlands, Luca Salis &
  Leonie Frank (German youth constitutional cases)** — by *embedding similarity*, not keywords.
  *"Analogues across jurisdictions and languages a keyword search misses."*
- Optionally `find_cases_by_law("Public Trust Doctrine")` → 88, *"Clean Air Act"* → 597 — the
  doctrinal map a litigator builds a 50-state / cross-border survey from.

---

## Beat 5 — Structured intelligence: parties + outcomes · ~2 min

- `get_case("Sabin.family.8918.0")` (*Milieudefensie v. Shell*) → **`outcome_code: mixed`**,
  structured **parties** (plaintiff / defendant), `core_object`, field-level provenance.
- **Be precise about the method (this is a strength, not a hedge):** outcomes are
  LLM-classified, **anchored to the latest disposition** (so Shell isn't mislabeled a plaintiff win
  off the overturned 2021 order), **confidence-gated, and every one backed by a verbatim quote** in
  provenance; uncertain cases are left blank rather than guessed. **~1,600 decided cases** carry an
  outcome; **92% of cases** have structured parties (both were 0% upstream).
- `get_statistics(scope="all")` → corpus totals; `get_statistics(group_by="jurisdiction")` for the
  distribution. (`get_case(..., include_documents=false)` keeps payloads light for an agent.)

---

## Beat 6 — Honesty / provenance · ~1 min

- `get_case(...)` → **field-level provenance** (`source`, `model`, `retrieved_at`, and for outcomes a
  `supporting_quote`), and a `citation_string` that links back to **climatecasechart.com** — never
  constructed by the model.
- Say the **as-of date out loud** (`2026-05-07`) and the pinned-provenance posture.
- **Hand over the one-page Data-Quality QA report** as a gift — including the upstream issues we
  found in your data (a sign we're a careful steward, not a scraper).

---

## Beat 7 — The asks · ~2 min

- **Sabin:**
  1. Bless a **citation-safe MCP layer over your *official* data**; confirm the litigation-corpus
     **licence / attribution** terms.
  2. An **official data feed** (API or bulk export) so we ingest from the source, not a mirror —
     this is the path to freshness.
  3. Include the **international / multilateral tracker** (the **ICJ AO, ITLOS AO, IACtHR OC-32/25**
     are the most-queried 2024–25 items and are currently absent from the litigation stream).
- **CPR:**
  1. Share your **case ↔ law concept mapping** — it makes `linked_statutes` comprehensive instead of
     the high-precision-but-partial title match we have now (145 links).
  2. Let us adopt your **`import_id` as the dedup key** and your **concept annotations**.
  3. Treat OpenClimateLaw as the **agent-distribution layer for your open CCLW corpus.**

---

## Demo-safe (verified 2026-06-29)

- **Apex cases retrieve #1 by name** — *Urgenda*, *Held v. State*, *Massachusetts v. EPA*,
  *KlimaSeniorinnen* all rank #1 (the old name-ranking problem is **fixed**).
- `get_document_text` — deep + paginated (the KlimaSeniorinnen Grand Chamber judgment is 809k chars).
- `check_claim_support` — strict verbatim matcher; `attest_response` — **global** citation coverage,
  catches fabricated quotes anywhere (incl. doubled-curly-quote delimiters).
- **Legislation:** `search_statutes` / `get_statute` (multilingual full text); `find_cases_by_law`.
- **`linked_statutes`** — on *named-climate-law* cases (Friends of the Earth → CCA 2008; Mexico
  youth case → its General Climate Law).
- `find_related_cases` — high-precision cross-jurisdiction analogues.
- **Outcomes** — corrected (Shell = `mixed`); **parties** populated.
- `jurisdiction="ECTHR"` / `"CJEU"` body codes now resolve (ECTHR → 16, CJEU → 8).

## DO NOT DEMO (known-fragile — verified)

- **`find_relevant_passage` on foreign-language or non-US flagship cases** → `no_match`. The full
  judgments are indexed but semantic embeddings are essentially off (0.06% of passages), so a
  conceptual claim that isn't lexically present misses. **Use English-language US cases for pinpoint.**
- **`linked_statutes` on famous rights cases** (Urgenda, Held) → empty. The 145 links cover
  *named-climate-law* cases. **Demo the bridge on Friends of the Earth / a framework-law case.**
- **`find_citations` / `find_cited_by` on flagships** → thin/near-empty. The citation graph is not
  yet a feature.
- **`sort="newest"`** — still shows some procedural-order dates (e.g. Shoalwater) as if decisions;
  fine to mention recency but **don't dwell**, and don't claim "newest *decided*."
- **Long descriptive name queries** — *"KlimaSeniorinnen Switzerland European Court of Human Rights"*
  surfaces the wrong cases; **use the short canonical name** ("KlimaSeniorinnen").
- **International advisory opinions** (ICJ / ITLOS / IACtHR) — **absent.** Don't promise them (it's
  an ask, not a feature).
- **Duplicate flagship records** — *Held v. State* and *Massachusetts v. EPA* have multiple family
  IDs; the #1-by-name can be a thinner variant. **Pull flagships by a pinned, dry-run-confirmed ID.**

## Pinned IDs (confirm in the morning dry-run)

| Case | ID | Use in |
|---|---|---|
| Urgenda Foundation v. State of the Netherlands | `Sabin.family.2823.0` | Beats 1, 4 |
| Energy-Intensive Mfrs v. EPA (pinpoint) | `Sabin.family.151.0` | Beat 2 |
| Friends of the Earth v. Secretary of State (linked_statutes) | `Sabin.family.7481.0` | Beat 3 |
| UK Climate Change Act 2008 (statute) | `CCLW.family.1755.0` | Beat 3 |
| Milieudefensie v. Shell (outcome=mixed) | `Sabin.family.8918.0` | Beat 5 |
| KlimaSeniorinnen | `Sabin.family.15540.0` | mention |
