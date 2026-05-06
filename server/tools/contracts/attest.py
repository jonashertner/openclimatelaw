from typing import Any

from server.db import get_pool
from server.tools.contracts.citation_formats import find_citation_spans


async def attest_response(draft_text: str, retrieved_ids: list[str]) -> dict[str, Any]:
    """Validate a draft response against the citation strings of retrieved cases.

    Substring-matches `draft_text` for citation-shaped strings (ECLI, BVerfGE, BGE,
    US reporter). Flags any match that is NOT also present in the union of
    `citation_string.text` values for cases identified by `retrieved_ids`.

    Args:
        draft_text: The LLM-generated text to validate.
        retrieved_ids: Case UUIDs or Sabin IDs the LLM claims to have retrieved.

    Returns:
        {
            passed: bool,
            violations: [{format, text, span: [start, end], reason}, ...],
        }
    """
    spans = find_citation_spans(draft_text)
    if not spans:
        return {"passed": True, "violations": []}

    retrieved_citation_texts: set[str] = set()
    if retrieved_ids:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Build query with IN clause. PostgreSQL requires a query literal
                # for type safety, so we construct the IN clause carefully.
                placeholders = ", ".join(["%s"] * len(retrieved_ids))
                params = list(retrieved_ids) + list(retrieved_ids)
                query = (
                    "SELECT cs.text "
                    "FROM citation_string cs "
                    "JOIN case_record c ON c.id = cs.case_id "
                    f"WHERE c.id::text IN ({placeholders}) "
                    f"OR c.sabin_id IN ({placeholders})"
                )
                await cur.execute(query, params)  # type: ignore[arg-type]
                rows = await cur.fetchall()
                for r in rows:
                    retrieved_citation_texts.add(r[0])

    violations: list[dict[str, Any]] = []
    for span in spans:
        # A citation is supported if its text appears as a substring of ANY retrieved
        # citation_string. Equality is too strict (formatting differences); substring is
        # the right granularity for ECLI ids embedded in fuller citations.
        if any(span.text in cs for cs in retrieved_citation_texts):
            continue
        violations.append(
            {
                "format": span.format_name,
                "text": span.text,
                "span": [span.start, span.end],
                "reason": (
                    "citation-shaped string not present in retrieved citation_strings"
                ),
            }
        )

    return {"passed": len(violations) == 0, "violations": violations}
