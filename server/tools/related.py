# pyright: basic
"""find_related_cases — semantic similarity over case_record embeddings.

Given a target case (by UUID or sabin_id), return the N cases whose summary
embeddings are nearest in cosine distance. Uses the case_record.embedding
column populated by ingest.embed (sentence-transformers/all-MiniLM-L6-v2).

Filters layer in optionally (jurisdiction, claim_type, status). Excludes
the target case itself.

Use cases:
- "What other cases are similar to Urgenda?" — find conceptually-close cases
  even if their titles share no keywords.
- "Other youth-plaintiff constitutional cases like this one."
- "Cases comparable to Held v. Montana in their reasoning."
"""

from typing import Any

from server.db import get_pool


async def find_related_cases(
    case_id_or_sabin_id: str,
    jurisdiction: str | None = None,
    claim_type: str | None = None,
    status: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return the N cases whose embeddings are nearest to the target's."""
    limit = max(1, min(50, int(limit)))
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Find the target's embedding
            await cur.execute(
                """
                SELECT id::text, canonical_title, embedding IS NULL AS no_embedding
                FROM case_record
                WHERE id::text = %s OR sabin_id = %s
                """,
                (case_id_or_sabin_id, case_id_or_sabin_id),
            )
            row = await cur.fetchone()
            if row is None:
                return {
                    "case_id": case_id_or_sabin_id,
                    "error": "case not found",
                    "count": 0,
                    "results": [],
                }
            target_id, target_title, no_embedding = row
            if no_embedding:
                return {
                    "case_id": case_id_or_sabin_id,
                    "target_title": target_title,
                    "error": "target case has no embedding",
                    "count": 0,
                    "results": [],
                }

            # Now find nearest neighbours via the HNSW index
            await cur.execute(
                """
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
                    1 - (c.embedding <=> (SELECT embedding FROM case_record WHERE id::text = %(target)s)) AS similarity
                FROM case_record c
                WHERE c.id::text != %(target)s
                  AND c.embedding IS NOT NULL
                  AND (%(jurisdiction)s::text IS NULL OR c.jurisdiction_code = %(jurisdiction)s::text)
                  AND (%(status)s::text IS NULL OR c.status_code = %(status)s::text)
                  AND (
                      %(claim_type)s::text IS NULL
                      OR EXISTS (
                          SELECT 1 FROM case_claim_type cct
                          WHERE cct.case_id = c.id AND cct.claim_type_code = %(claim_type)s::text
                      )
                  )
                ORDER BY c.embedding <=> (SELECT embedding FROM case_record WHERE id::text = %(target)s)
                LIMIT %(limit)s
                """,
                {
                    "target": target_id,
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
            "similarity": float(r[9]) if r[9] is not None else 0.0,
        }
        for r in rows
    ]
    return {
        "case_id": case_id_or_sabin_id,
        "target_title": target_title,
        "filters": {
            "jurisdiction": jurisdiction,
            "claim_type": claim_type,
            "status": status,
        },
        "count": len(results),
        "results": results,
    }
