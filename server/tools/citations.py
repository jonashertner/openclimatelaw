"""find_citations / find_cited_by — case-to-case citation graph queries.

Reads from citation_edge populated by ingest.citation_graph. Returns the
cases A cites (forward edges) or the cases that cite A (backward edges),
each with the verbatim citation text and the source_of_edge tag so the LLM
knows whether the link came from a Sabin-structured reference or NLP
extraction over text.
"""

from typing import Any

from server.db import get_pool


async def find_citations(case_id_or_sabin_id: str, limit: int = 50) -> dict[str, Any]:
    """Return cases that the given case cites."""
    limit = max(1, min(200, int(limit)))
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                WITH src AS (
                    SELECT id FROM case_record
                    WHERE id::text = %(q)s OR sabin_id = %(q)s
                )
                SELECT
                    cited.id::text,
                    cited.sabin_id,
                    cited.canonical_title,
                    cited.jurisdiction_code,
                    e.citation_string,
                    e.source_of_edge,
                    count(*) OVER () AS total
                FROM citation_edge e
                JOIN case_record cited ON cited.id = e.cited_case_id
                WHERE e.citing_case_id = (SELECT id FROM src)
                ORDER BY cited.canonical_title
                LIMIT %(limit)s
                """,
                {"q": case_id_or_sabin_id, "limit": limit},
            )
            rows = await cur.fetchall()

    if not rows:
        return {"case_id": case_id_or_sabin_id, "count": 0, "results": []}
    total = rows[0][6] if rows else 0
    return {
        "case_id": case_id_or_sabin_id,
        "count": len(rows),
        "total": int(total),
        "results": [
            {
                "id": r[0],
                "sabin_id": r[1],
                "canonical_title": r[2],
                "jurisdiction_code": r[3],
                "citation_string": r[4],
                "source_of_edge": r[5],
            }
            for r in rows
        ],
    }


async def find_cited_by(case_id_or_sabin_id: str, limit: int = 50) -> dict[str, Any]:
    """Return cases that cite the given case."""
    limit = max(1, min(200, int(limit)))
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                WITH src AS (
                    SELECT id FROM case_record
                    WHERE id::text = %(q)s OR sabin_id = %(q)s
                )
                SELECT
                    citing.id::text,
                    citing.sabin_id,
                    citing.canonical_title,
                    citing.jurisdiction_code,
                    e.citation_string,
                    e.source_of_edge,
                    count(*) OVER () AS total
                FROM citation_edge e
                JOIN case_record citing ON citing.id = e.citing_case_id
                WHERE e.cited_case_id = (SELECT id FROM src)
                ORDER BY citing.canonical_title
                LIMIT %(limit)s
                """,
                {"q": case_id_or_sabin_id, "limit": limit},
            )
            rows = await cur.fetchall()

    if not rows:
        return {"case_id": case_id_or_sabin_id, "count": 0, "results": []}
    total = rows[0][6] if rows else 0
    return {
        "case_id": case_id_or_sabin_id,
        "count": len(rows),
        "total": int(total),
        "results": [
            {
                "id": r[0],
                "sabin_id": r[1],
                "canonical_title": r[2],
                "jurisdiction_code": r[3],
                "citation_string": r[4],
                "source_of_edge": r[5],
            }
            for r in rows
        ],
    }
