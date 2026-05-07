# CCLW Direct Ingestion — Research Brief

**Date**: 2026-05-07
**Question**: How do we ingest Climate Change Laws of the World (CCLW)
without the CPR API?

## Verdict

**Use HuggingFace dataset `ClimatePolicyRadar/all-document-text-data`**.
This is the publisher's own canonical open release of the same corpus the
CPR API would serve — "direct from publisher" by exactly the same standard
as Fedlex SPARQL is for Swiss law. CC-BY 4.0. No API, no JS scrape, no
partnership ask.

## Path Forward

1. `uv add datasets pyarrow` and load via `datasets.load_dataset(
   "ClimatePolicyRadar/all-document-text-data")`. Or pull parquet shards
   directly via the HF resolve URL.
2. Schema is text-block oriented: rows are `text_block_*` records with
   page coordinates and family/document IDs. Aggregate by `document_family`
   to reconstruct law / case records.
3. Cross-reference back to canonical public URLs:
   - `climate-laws.org/document/<id>` for laws
   - `climatecasechart.com/document/<slug>` for litigation
   IDs are deterministic; both sites accept the family slug.
4. **Cross-validate** our existing Sabin ingest against the CPR side:
   `github.com/climatepolicyradar/litigation-data-mapper` documents the
   field mapping from Sabin → CPR family schema. Useful for dedupe.

## Side-channel: CPR API

The public Climate Policy Radar API is **not actually open self-serve as
of now** (still "coming soon" per CPR marketing). So even if we'd allowed
it, it isn't a production-viable source today. Moot.

## Friction

- **HF dataset**: low. Multi-GB parquet, standard tooling. Update cadence
  is periodic batch — record `dataset_revision` per ingested row and
  re-pull quarterly.
- **Schema impedance**: text-block oriented, not row-per-document. Need
  aggregation step.
- **Climate-laws.org `__NEXT_DATA__` scrape**: pages don't embed a usable
  JSON blob the way Sabin's site does. XHR backend is undocumented Vespa
  search — fragile, likely against ToS.
- **Wayback CDX**: incomplete coverage of dynamic pages. Fallback only.
- **QoG DataFinder CCL CSV** (`datafinder.qog.gu.se/dataset/ccl`): useful
  for structured law metadata (sector flags, year passed, etc.) but no
  full text. Supplement only.
- **Licensing**: CC-BY 4.0 — preserve attribution to CPR + Grantham + Sabin
  in our outputs.

## Concrete Next Steps (when ready)

1. Add `datasets` and `pyarrow` to deps.
2. Write `ingest/cclw/hf_dataset.py` with: download, schema mapping,
   family aggregation, upsert into our `case_record` (litigation) and
   future `legislation_record` (laws) tables.
3. Pin a HF dataset revision so we can reproduce later.
4. Stretch: dedupe the Sabin-side cases against CPR-side cases by
   `import_id` / slug — we'd want to merge the two views into one record
   per case rather than have two rows for the same lawsuit.

## Sources

- [ClimatePolicyRadar/all-document-text-data on HuggingFace](https://huggingface.co/datasets/ClimatePolicyRadar/all-document-text-data)
- [climatepolicyradar/open-data](https://github.com/climatepolicyradar/open-data) — companion notebooks
- [climatepolicyradar/litigation-data-mapper](https://github.com/climatepolicyradar/litigation-data-mapper) — Sabin → CPR field mapping
- [Climate Litigation Database relaunch announcement](https://www.climatepolicyradar.org/latest/climate-litigation-database-relaunches-today)
- [CCLW Terms of Use (LSE Grantham)](https://www.lse.ac.uk/granthaminstitute/cclw-terms-and-conditions/)
- [climate-laws.org methodology](https://climate-laws.org/methodology)
- [QoG DataFinder CCL dataset](https://datafinder.qog.gu.se/dataset/ccl)
