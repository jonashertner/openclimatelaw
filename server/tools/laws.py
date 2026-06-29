# pyright: basic
"""find_cases_by_law — the legislation -> litigation reverse link.

Sabin tags each case with the principal laws/instruments it turns on
(concept_preferred_label 'principal_law/...'). get_case surfaces those per case;
this tool inverts the link: every case invoking a given law — e.g. 'which climate
cases turn on the Public Trust Doctrine / the Clean Air Act / the European
Convention on Human Rights?'. The legislation-centric view of the corpus, built
from data already ingested (no statute-text corpus required).
"""

from typing import Any

from server.db import get_pool

_FIND_BY_LAW_SQL = """
    SELECT
        c.id::text, c.sabin_id, c.canonical_title, c.jurisdiction_code,
        c.status_code, c.decision_date,
        (
            SELECT text FROM citation_string
            WHERE case_id = c.id AND lang = 'en' ORDER BY format LIMIT 1
        ) AS citation_string,
        EXISTS (SELECT 1 FROM case_doctrine cd WHERE cd.case_id = c.id) AS has_doctrine,
        count(*) OVER() AS total
    FROM case_record c
    WHERE c.primary_source IS DISTINCT FROM 'climate_rights'
      AND EXISTS (
        SELECT 1
        FROM jsonb_array_elements_text(
                 c.upstream_metadata->'metadata'->'concept_preferred_label'
             ) e
        WHERE e ILIKE 'principal_law/%%' || %(law)s || '%%'
      )
    ORDER BY c.decision_date DESC NULLS LAST, c.canonical_title
    LIMIT %(limit)s
"""


async def find_cases_by_law(law: str, limit: int = 20) -> dict[str, Any]:
    """Return climate cases whose principal-law tags match `law` (case-insensitive substring)."""
    law = (law or "").strip()
    if not law:
        return {"law": law, "count": 0, "total": 0, "results": []}
    limit = max(1, min(50, int(limit)))
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_FIND_BY_LAW_SQL, {"law": law, "limit": limit})
            rows = await cur.fetchall()
    total = rows[0][8] if rows else 0
    results = [
        {
            "id": r[0],
            "sabin_id": r[1],
            "canonical_title": r[2],
            "jurisdiction_code": r[3],
            "status_code": r[4],
            "decision_date": r[5].isoformat() if r[5] else None,
            "citation_string": r[6],
            "has_doctrine": bool(r[7]),
        }
        for r in rows
    ]
    return {"law": law, "count": len(results), "total": total, "results": results}
