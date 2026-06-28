# pyright: basic
"""Query the CCLW legislation layer (the `statute` table).

search_statutes: title-weighted full-text search over CCLW laws & policies.
get_statute: one law's record + paginated verbatim text (like get_document_text).
"""

from typing import Any

from server.db import get_pool

_TSV = (
    "setweight(to_tsvector('simple', s.short_title), 'A') "
    "|| setweight(to_tsvector('simple', coalesce(s.text, '')), 'D')"
)

_SEARCH_SQL = f"""
    WITH q AS (SELECT plainto_tsquery('simple', %(query)s) AS tsq)
    SELECT s.id::text, s.cclw_id, s.short_title, s.jurisdiction_code, s.status,
           s.enacted_date,
           ts_headline('simple', coalesce(s.text, ''), (SELECT tsq FROM q),
               'StartSel=<b>, StopSel=</b>, MaxFragments=2, MaxWords=18') AS snippet,
           ts_rank('{{0.1, 0.2, 0.4, 1.0}}', {_TSV}, (SELECT tsq FROM q)) AS rank,
           count(*) OVER() AS total
    FROM statute s, q
    WHERE ({_TSV}) @@ (SELECT tsq FROM q)
      AND (%(jur)s::text IS NULL OR s.jurisdiction_code = %(jur)s::text)
    ORDER BY rank DESC, s.short_title
    LIMIT %(limit)s
"""

_MAX_WINDOW = 20000


async def search_statutes(
    query: str, jurisdiction: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """Search CCLW laws & policies by title + text. Returns matches + total count."""
    query = (query or "").strip()
    if not query:
        return {"query": query, "count": 0, "total": 0, "results": []}
    limit = max(1, min(50, int(limit)))
    if jurisdiction is not None:
        jurisdiction = jurisdiction.strip().upper() or None
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_SEARCH_SQL, {"query": query, "jur": jurisdiction, "limit": limit})
            rows = await cur.fetchall()
    total = rows[0][8] if rows else 0
    results = [
        {
            "id": r[0],
            "cclw_id": r[1],
            "short_title": r[2],
            "jurisdiction_code": r[3],
            "status": r[4],
            "enacted_date": r[5].isoformat() if r[5] else None,
            "match_snippet": r[6],
        }
        for r in rows
    ]
    return {"query": query, "count": len(results), "total": total, "results": results}


async def get_statute(
    cclw_id_or_id: str, offset: int = 0, max_chars: int = 8000
) -> dict[str, Any] | None:
    """Return one CCLW law's record + a paginated window of its verbatim text."""
    max_chars = max(1, min(_MAX_WINDOW, int(max_chars)))
    offset = max(0, int(offset))
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id::text, cclw_id, jurisdiction_code, short_title, long_title,
                       enacted_date, status, text_lang, text
                FROM statute
                WHERE cclw_id = %s OR id::text = %s
                """,
                (cclw_id_or_id, cclw_id_or_id),
            )
            row = await cur.fetchone()
    if row is None:
        return None
    full = row[8] or ""
    window = full[offset : offset + max_chars]
    return {
        "id": row[0],
        "cclw_id": row[1],
        "jurisdiction_code": row[2],
        "short_title": row[3],
        "long_title": row[4],
        "enacted_date": row[5].isoformat() if row[5] else None,
        "status": row[6],
        "text_lang": row[7],
        "total_chars": len(full),
        "offset": offset,
        "returned_chars": len(window),
        "has_more": offset + max_chars < len(full),
        "next_offset": offset + max_chars if offset + max_chars < len(full) else None,
        "text": window,
    }
