from typing import Any

from server.db import get_pool


async def cite(case_id: str, lang: str, format: str) -> dict[str, Any] | None:
    """Return the canonical citation_string for a case in the requested language and format.

    Args:
        case_id: The canonical UUID or Sabin ID. Required (R1 enforcement: callers
            must already hold a valid case_id obtained from a search/get tool).
        lang: ISO 639-1 language code (e.g. 'en', 'nl', 'de').
        format: Citation format name (e.g. 'sabin', 'native', 'bluebook', 'oscola').

    Returns:
        {citation_string, lang, format, case_id} on hit, or None when no row matches.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT cs.text, c.id
                FROM citation_string cs
                JOIN case_record c ON c.id = cs.case_id
                WHERE (c.id::text = %s OR c.sabin_id = %s)
                  AND cs.lang = %s
                  AND cs.format = %s
                """,
                (case_id, case_id, lang, format),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            citation_text, case_uuid = row

    return {
        "citation_string": citation_text,
        "lang": lang,
        "format": format,
        "case_id": str(case_uuid),
    }
