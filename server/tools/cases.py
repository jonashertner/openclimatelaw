from typing import Any

from server.db import get_pool


async def get_case(case_id_or_sabin_id: str) -> dict[str, Any] | None:
    """Return a case record by canonical UUID or by Sabin ID, or None if not found."""

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, sabin_id, canonical_title, jurisdiction_code, court_id,
                       filing_date, decision_date, status_code, outcome_code,
                       summary, summary_lang, primary_source, provenance, updated_at
                FROM case_record
                WHERE id::text = %s OR sabin_id = %s
                """,
                (case_id_or_sabin_id, case_id_or_sabin_id),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            (
                _id, sabin_id, canonical_title, jurisdiction_code, court_id,
                filing_date, decision_date, status_code, outcome_code,
                summary, summary_lang, primary_source, provenance, updated_at,
            ) = row

            await cur.execute(
                """
                SELECT side, name, party_type, ord
                FROM case_party
                WHERE case_id = %s
                ORDER BY side, ord
                """,
                (str(_id),),
            )
            parties = [
                {"side": r[0], "name": r[1], "party_type": r[2], "ord": r[3]}
                for r in await cur.fetchall()
            ]

            await cur.execute(
                "SELECT claim_type_code FROM case_claim_type"
                " WHERE case_id = %s ORDER BY claim_type_code",
                (str(_id),),
            )
            claim_types = [r[0] for r in await cur.fetchall()]

            await cur.execute(
                """
                SELECT id, category_code, title, filed_date, filed_by, upstream_url, storage_url
                FROM document
                WHERE case_id = %s
                ORDER BY filed_date NULLS LAST, title
                """,
                (str(_id),),
            )
            documents = [
                {
                    "id": str(r[0]),
                    "category_code": r[1],
                    "title": r[2],
                    "filed_date": r[3].isoformat() if r[3] else None,
                    "filed_by": r[4],
                    "upstream_url": r[5],
                    "storage_url": r[6],
                }
                for r in await cur.fetchall()
            ]

            await cur.execute(
                "SELECT lang, format, text FROM citation_string"
                " WHERE case_id = %s ORDER BY lang, format",
                (str(_id),),
            )
            citation_strings = [
                {"lang": r[0], "format": r[1], "text": r[2]}
                for r in await cur.fetchall()
            ]

    return {
        "id": str(_id),
        "sabin_id": sabin_id,
        "canonical_title": canonical_title,
        "jurisdiction_code": jurisdiction_code,
        "court_id": court_id,
        "filing_date": filing_date.isoformat() if filing_date else None,
        "decision_date": decision_date.isoformat() if decision_date else None,
        "status_code": status_code,
        "outcome_code": outcome_code,
        "summary": summary,
        "summary_lang": summary_lang,
        "primary_source": primary_source,
        "provenance": provenance,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "parties": parties,
        "claim_types": claim_types,
        "documents": documents,
        "citation_strings": citation_strings,
    }
