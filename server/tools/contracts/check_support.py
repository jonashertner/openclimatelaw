from typing import Any, Literal

from server.db import get_pool

SourceKind = Literal["case_summary", "document_text", "citation_string"]
VALID_SOURCE_KINDS: set[str] = {"case_summary", "document_text", "citation_string"}


async def check_claim_support(quote: str, source_id: str, source_kind: str) -> dict[str, Any]:
    """Validate that `quote` appears verbatim in the named source's text.

    Args:
        quote: The exact text to search for.
        source_id: For case_summary -> case UUID or sabin_id.
                   For document_text -> document UUID.
                   For citation_string -> case UUID or sabin_id.
        source_kind: 'case_summary' | 'document_text' | 'citation_string'.

    Returns:
        {supported: bool, reason: str, source_id: str, source_kind: str}.
    """
    if source_kind not in VALID_SOURCE_KINDS:
        raise ValueError(
            f"invalid source_kind: {source_kind!r} (must be one of {sorted(VALID_SOURCE_KINDS)})"
        )
    # Empty/whitespace-only quote: vacuously a substring of everything; reject explicitly.
    if not quote or not quote.strip():
        return {
            "supported": False,
            "reason": "empty quote — supply non-whitespace text to validate",
            "source_id": source_id,
            "source_kind": source_kind,
        }

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            haystack: str | None = None
            if source_kind == "case_summary":
                await cur.execute(
                    "SELECT summary FROM case_record WHERE id::text = %s OR sabin_id = %s",
                    (source_id, source_id),
                )
                row = await cur.fetchone()
                haystack = row[0] if row else None
            elif source_kind == "document_text":
                await cur.execute(
                    "SELECT text FROM document WHERE id::text = %s",
                    (source_id,),
                )
                row = await cur.fetchone()
                haystack = row[0] if row else None
            elif source_kind == "citation_string":
                await cur.execute(
                    """
                    SELECT cs.text
                    FROM citation_string cs
                    JOIN case_record c ON c.id = cs.case_id
                    WHERE c.id::text = %s OR c.sabin_id = %s
                    """,
                    (source_id, source_id),
                )
                rows = await cur.fetchall()
                haystack = "\n".join(r[0] for r in rows) if rows else None

    if haystack is None:
        return {
            "supported": False,
            "reason": f"source not found: source_kind={source_kind} source_id={source_id}",
            "source_id": source_id,
            "source_kind": source_kind,
        }

    if quote in haystack:
        return {
            "supported": True,
            "reason": "verbatim substring match",
            "source_id": source_id,
            "source_kind": source_kind,
        }

    return {
        "supported": False,
        "reason": f"quote not found in {source_kind}",
        "source_id": source_id,
        "source_kind": source_kind,
    }
