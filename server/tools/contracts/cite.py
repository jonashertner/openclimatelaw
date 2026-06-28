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
            if row is not None:
                citation_text, case_uuid = row
                return {
                    "citation_string": citation_text,
                    "lang": lang,
                    "format": format,
                    "case_id": str(case_uuid),
                }
            # Fallback: the requested lang/format has no row, but never return a silent
            # null that might tempt the model to fabricate — give the case's best
            # available citation (prefer the requested lang, then English, then 'sabin').
            await cur.execute(
                """
                SELECT cs.text, c.id, cs.lang, cs.format
                FROM citation_string cs
                JOIN case_record c ON c.id = cs.case_id
                WHERE c.id::text = %s OR c.sabin_id = %s
                ORDER BY (cs.lang = %s) DESC, (cs.lang = 'en') DESC, (cs.format = 'sabin') DESC
                LIMIT 1
                """,
                (case_id, case_id, lang),
            )
            fb = await cur.fetchone()

    if fb is None:
        return None
    fb_text, fb_uuid, fb_lang, fb_format = fb
    return {
        "citation_string": fb_text,
        "lang": fb_lang,
        "format": fb_format,
        "case_id": str(fb_uuid),
        "requested_format": format,
        "fallback": True,
    }
