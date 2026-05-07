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
                       summary, summary_lang, primary_source, provenance, updated_at,
                       upstream_metadata
                FROM case_record
                WHERE id::text = %s OR sabin_id = %s
                """,
                (case_id_or_sabin_id, case_id_or_sabin_id),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            (
                _id,
                sabin_id,
                canonical_title,
                jurisdiction_code,
                court_id,
                filing_date,
                decision_date,
                status_code,
                outcome_code,
                summary,
                summary_lang,
                primary_source,
                provenance,
                updated_at,
                upstream_metadata,
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
                {"lang": r[0], "format": r[1], "text": r[2]} for r in await cur.fetchall()
            ]

    case_number, core_object, principal_laws = _project_upstream_metadata(upstream_metadata)

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
        "case_number": case_number,
        "core_object": core_object,
        "principal_laws": principal_laws,
        "parties": parties,
        "claim_types": claim_types,
        "documents": documents,
        "citation_strings": citation_strings,
        "upstream_metadata": upstream_metadata,
    }


def _project_upstream_metadata(
    upstream_metadata: dict[str, Any] | None,
) -> tuple[str | None, str | None, list[str]]:
    """Pull the most useful fields out of the upstream blob into top-level surface area.

    - case_number: docket / formal cite from upstream (e.g. ECLI, US reporter)
    - core_object: one-sentence holding/issue text
    - principal_laws: statutes the case turns on (from concept_preferred_label)
    """
    if not upstream_metadata:
        return None, None, []
    md = upstream_metadata.get("metadata") or {}

    case_number_list = md.get("case_number") or []
    case_number = case_number_list[0] if case_number_list else None

    core_object_list = md.get("core_object") or []
    core_object = core_object_list[0] if core_object_list else None

    principal_laws: list[str] = []
    for label in md.get("concept_preferred_label") or []:
        if isinstance(label, str) and label.startswith("principal_law/"):
            principal_laws.append(label.removeprefix("principal_law/"))

    return case_number, core_object, principal_laws
