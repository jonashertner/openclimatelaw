# pyright: basic
"""get_case_doctrine — the structured, verifiable doctrinal record for a case.

Returns disposition (+ posture), holdings (each with a verified flag), the legal test,
legal bases, relief, and significance, plus provenance and a quotes_verified/quotes_total
score. Every quoted element was checked verbatim against the source; significance is
interpretive synthesis. Populated by ingest/doctrine.py.
"""

from typing import Any

from server.db import get_pool


async def get_case_doctrine(case_id_or_sabin_id: str) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM case_record WHERE id::text = %s OR sabin_id = %s",
            (case_id_or_sabin_id, case_id_or_sabin_id),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        case_id = row[0]
        await cur.execute(
            """
            SELECT disposition_outcome, disposition_posture, disposition_quote, holdings,
                   legal_test, legal_test_quote, legal_bases, relief, relief_quote,
                   significance, source_kind, model, quotes_total, quotes_verified, extracted_at
            FROM case_doctrine WHERE case_id = %s::uuid
            """,
            (case_id,),
        )
        d = await cur.fetchone()
    if d is None:
        return {
            "case_id": case_id,
            "available": False,
            "note": "no doctrine record extracted for this case yet",
        }
    return {
        "case_id": case_id,
        "available": True,
        "disposition": {"outcome": d[0], "posture": d[1], "quote": d[2]},
        "holdings": d[3],
        "legal_test": ({"test": d[4], "quote": d[5]} if d[4] else None),
        "legal_bases": d[6],
        "relief": ({"relief": d[7], "quote": d[8]} if d[7] else None),
        "significance": d[9],
        "provenance": {
            "source": "llm",
            "model": d[11],
            "source_kind": d[10],
            "quotes_verified": d[13],
            "quotes_total": d[12],
            "extracted_at": d[14].isoformat() if d[14] else None,
        },
    }
