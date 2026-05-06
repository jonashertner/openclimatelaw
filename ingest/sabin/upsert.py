from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ingest.sabin.parse import ParsedCase


async def upsert_case(pool: AsyncConnectionPool, parsed: ParsedCase) -> str:
    """Insert or update a case, replacing all child rows. Returns the case UUID."""

    case = parsed.case
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO case_record (
                        sabin_id, canonical_title, jurisdiction_code, court_id,
                        filing_date, decision_date, status_code, outcome_code,
                        summary, summary_lang, primary_source, provenance, updated_at
                    )
                    VALUES (%(sabin_id)s, %(canonical_title)s, %(jurisdiction_code)s,
                            %(court_id)s, %(filing_date)s, %(decision_date)s,
                            %(status_code)s, %(outcome_code)s, %(summary)s,
                            %(summary_lang)s, %(primary_source)s, %(provenance)s, now())
                    ON CONFLICT (sabin_id) DO UPDATE SET
                        canonical_title = EXCLUDED.canonical_title,
                        jurisdiction_code = EXCLUDED.jurisdiction_code,
                        court_id = EXCLUDED.court_id,
                        filing_date = EXCLUDED.filing_date,
                        decision_date = EXCLUDED.decision_date,
                        status_code = EXCLUDED.status_code,
                        outcome_code = EXCLUDED.outcome_code,
                        summary = EXCLUDED.summary,
                        summary_lang = EXCLUDED.summary_lang,
                        primary_source = EXCLUDED.primary_source,
                        provenance = EXCLUDED.provenance,
                        updated_at = now()
                    RETURNING id
                    """,
                    {**case, "provenance": Jsonb(case["provenance"])},
                )
                row = await cur.fetchone()
                assert row is not None
                case_id: str = str(row[0])

                await cur.execute("DELETE FROM case_party WHERE case_id = %s", (case_id,))
                await cur.execute(
                    "DELETE FROM case_claim_type WHERE case_id = %s", (case_id,)
                )
                await cur.execute("DELETE FROM document WHERE case_id = %s", (case_id,))
                await cur.execute(
                    "DELETE FROM citation_string WHERE case_id = %s", (case_id,)
                )

                for party in parsed.parties:
                    await cur.execute(
                        """
                        INSERT INTO case_party (case_id, side, name, party_type, ord)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (case_id, party["side"], party["name"], party["party_type"], party["ord"]),
                    )

                for claim_code in parsed.claim_type_codes:
                    await cur.execute(
                        """
                        INSERT INTO case_claim_type (case_id, claim_type_code)
                        VALUES (%s, %s)
                        """,
                        (case_id, claim_code),
                    )

                for doc in parsed.documents:
                    await cur.execute(
                        """
                        INSERT INTO document (
                            case_id, category_code, title, filed_date, filed_by,
                            upstream_url, provenance, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            case_id,
                            doc["category_code"],
                            doc["title"],
                            doc["filed_date"],
                            doc["filed_by"],
                            doc["upstream_url"],
                            Jsonb(doc["provenance"]),
                        ),
                    )

                for cs in parsed.citation_strings:
                    await cur.execute(
                        """
                        INSERT INTO citation_string (case_id, lang, format, text)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (case_id, cs["lang"], cs["format"], cs["text"]),
                    )

    return case_id
