from typing import Any

from server.db import get_pool

_MAX_WINDOW = 20000


async def get_document_text(
    document_id: str, offset: int = 0, max_chars: int = 8000
) -> dict[str, Any] | None:
    """Return a window of a document's verbatim extracted text, with its case citation.

    Documents (court opinions, filings) carry the full extracted decision text. This
    is the verbatim source an agent quotes from — pair it with check_claim_support
    (source_kind='document_text') to verify a quote before using it. Long decisions
    are paginated via offset + max_chars (max 20000); follow `has_more` / `next_offset`.

    Args:
        document_id: the document UUID (from get_case().documents[].id).
        offset: starting character offset into the text.
        max_chars: window size (clamped to 1..20000).

    Returns:
        {document_id, case_id, title, case_title, citation_string, total_chars,
         offset, returned_chars, has_more, next_offset, text} or None if not found.
    """
    offset = max(0, int(offset))
    max_chars = max(1, min(_MAX_WINDOW, int(max_chars)))

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    d.id::text,
                    d.case_id::text,
                    d.title,
                    d.text,
                    c.canonical_title,
                    (
                        SELECT cs.text FROM citation_string cs
                        WHERE cs.case_id = c.id
                        ORDER BY (cs.lang = 'en') DESC, cs.format
                        LIMIT 1
                    )
                FROM document d
                JOIN case_record c ON c.id = d.case_id
                WHERE d.id::text = %s
                """,
                (document_id,),
            )
            row = await cur.fetchone()

    if row is None:
        return None

    doc_id, case_id, title, text, case_title, citation = row
    text = text or ""
    total = len(text)
    window = text[offset : offset + max_chars]
    has_more = offset + max_chars < total

    return {
        "document_id": doc_id,
        "case_id": case_id,
        "title": title,
        "case_title": case_title,
        "citation_string": citation,
        "total_chars": total,
        "offset": offset,
        "returned_chars": len(window),
        "has_more": has_more,
        "next_offset": offset + len(window) if has_more else None,
        "text": window,
    }
