# pyright: basic
"""Cross-link cases to the CCLW statutes they invoke (case_statute).

A case's principal_law tags (concept_preferred_label 'principal_law/<name>') are
matched to ingested CCLW statutes by exact title + jurisdiction, after stripping a
trailing abbreviation ("Clean Air Act (CAA)" -> "Clean Air Act"). High precision:
this links e.g. UK climate cases to the actual Climate Change Act 2008 (full text in
the statute table). Coverage is intentionally partial — only cases invoking a named
law that CCLW catalogs (climate-framework laws) link; general statutes CCLW doesn't
catalog (e.g. NEPA) don't. Idempotent. Run: uv run python -m ingest.cross_link
"""

from __future__ import annotations

import asyncio
import sys

import structlog

log = structlog.get_logger("ingest.cross_link")

# Match each case's principal_law tag to a statute of the same jurisdiction by exact
# title (case-insensitive), stripping a trailing "(ABBREV)" from the tag.
_BACKFILL = r"""
    INSERT INTO case_statute (case_id, statute_id, relationship, source_of_link)
    SELECT DISTINCT cr.id, s.id, 'referenced', 'principal_law_title_match'
    FROM case_record cr,
         jsonb_array_elements_text(
             cr.upstream_metadata->'metadata'->'concept_preferred_label'
         ) AS e,
         statute s
    WHERE cr.primary_source IS DISTINCT FROM 'climate_rights'
      AND e LIKE 'principal_law/%'
      AND s.jurisdiction_code = cr.jurisdiction_code
      AND lower(s.short_title) = lower(
            trim(regexp_replace(
                regexp_replace(e, '^principal_law/', ''),
                '\s*\([^)]*\)\s*$', ''
            ))
          )
    ON CONFLICT DO NOTHING
"""


async def backfill_case_statutes() -> dict[str, int]:
    from server.db import get_pool

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_BACKFILL)
            linked = cur.rowcount
            await cur.execute("SELECT count(DISTINCT case_id) FROM case_statute")
            row = await cur.fetchone()
        await conn.commit()
    cases = row[0] if row else 0
    log.info("cross_link_complete", linked=linked, cases_linked=cases)
    return {"linked": linked, "cases_linked": cases}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await backfill_case_statutes()
        finally:
            await close_pool()

    print(f"DONE: {asyncio.run(runner())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
