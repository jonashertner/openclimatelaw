"""search_cases — hybrid full-text + trigram fuzzy search across case titles
and summaries.

The major usability gap before this tool: LLMs could only retrieve cases by
sabin_id (e.g. Sabin.family.9998.0) or canonical UUID. Without knowing those,
'find Urgenda v. Netherlands' had no way to land on the right record. Now an
LLM can call search_cases('Urgenda Netherlands') and get back ranked matches.

Hybrid scoring (each row gets the max of the two):
- FTS rank — Postgres `to_tsvector` + `plainto_tsquery` for tokenized matching.
  Catches topic searches: 'youth plaintiffs', 'Amazon deforestation'.
- Trigram similarity — pg_trgm `similarity(canonical_title, query)`. Catches
  typos and partial case names: 'klimasenoirinnen' -> KlimaSeniorinnen.

The final rank is `GREATEST(fts_rank * 10, trigram_sim)` (FTS scaled up so
strong topic matches still beat weak fuzzy title matches).

Filters (jurisdiction, claim_type, status) layer on as additional WHERE.

Returns ranked matches with the canonical citation_string so the LLM has a
verbatim citation to use immediately — closing the loop with the R1 contract.
"""

from typing import Any

from server.db import get_pool


async def search_cases(
    query: str,
    jurisdiction: str | None = None,
    claim_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search cases by free-text against title + summary, with optional filters."""
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    limit = max(1, min(50, int(limit)))

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Hybrid: FTS over title+summary OR trigram similarity on title.
            # FTS rank is scaled (x10) so strong topic matches outrank weak
            # fuzzy matches. Trigram threshold of 0.2 catches reasonable typos
            # without flooding results with unrelated cases.
            sql = """
                WITH q AS (
                    SELECT
                        plainto_tsquery('simple', %(query)s) AS tsq,
                        %(query)s AS qstr
                )
                SELECT * FROM (
                    SELECT
                        c.id::text,
                        c.sabin_id,
                        c.canonical_title,
                        c.jurisdiction_code,
                        c.court_id,
                        c.status_code,
                        c.outcome_code,
                        substring(c.summary FROM 1 FOR 240) AS summary_excerpt,
                        (
                            SELECT text FROM citation_string
                            WHERE case_id = c.id AND lang = 'en'
                            ORDER BY format LIMIT 1
                        ) AS citation_string,
                        ts_rank(
                            to_tsvector(
                                'simple',
                                c.canonical_title || ' ' || coalesce(c.summary, '')
                            ),
                            (SELECT tsq FROM q)
                        ) AS fts_rank,
                        similarity(c.canonical_title, (SELECT qstr FROM q)) AS trgm_sim,
                        GREATEST(
                            ts_rank(
                                to_tsvector(
                                    'simple',
                                    c.canonical_title || ' ' || coalesce(c.summary, '')
                                ),
                                (SELECT tsq FROM q)
                            ) * 10.0,
                            similarity(c.canonical_title, (SELECT qstr FROM q))
                        ) AS rank
                    FROM case_record c, q
                    WHERE
                        (
                            to_tsvector(
                                'simple',
                                c.canonical_title || ' ' || coalesce(c.summary, '')
                            ) @@ q.tsq
                            OR similarity(c.canonical_title, q.qstr) > 0.2
                        )
                        AND (%(jurisdiction)s::text IS NULL OR c.jurisdiction_code = %(jurisdiction)s::text)
                        AND (%(status)s::text IS NULL OR c.status_code = %(status)s::text)
                        AND (
                            %(claim_type)s::text IS NULL
                            OR EXISTS (
                                SELECT 1 FROM case_claim_type cct
                                WHERE cct.case_id = c.id AND cct.claim_type_code = %(claim_type)s::text
                            )
                        )
                ) ranked
                ORDER BY rank DESC, canonical_title
                LIMIT %(limit)s
            """
            await cur.execute(
                sql,
                {
                    "query": query,
                    "jurisdiction": jurisdiction,
                    "claim_type": claim_type,
                    "status": status,
                    "limit": limit,
                },
            )
            rows = await cur.fetchall()

    results = [
        {
            "id": r[0],
            "sabin_id": r[1],
            "canonical_title": r[2],
            "jurisdiction_code": r[3],
            "court_id": r[4],
            "status_code": r[5],
            "outcome_code": r[6],
            "summary_excerpt": r[7],
            "citation_string": r[8],
            "fts_rank": float(r[9]) if r[9] is not None else 0.0,
            "trigram_sim": float(r[10]) if r[10] is not None else 0.0,
            "rank": float(r[11]) if r[11] is not None else 0.0,
        }
        for r in rows
    ]

    return {
        "query": query,
        "filters": {
            "jurisdiction": jurisdiction,
            "claim_type": claim_type,
            "status": status,
        },
        "count": len(results),
        "results": results,
    }
