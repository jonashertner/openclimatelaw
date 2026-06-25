import re
from typing import Any

from server.db import get_pool
from server.tools.contracts.citation_formats import find_citation_spans

# A quoted span is "load-bearing" at this length; shorter quotes are too common
# (defined terms, single words) to audit without false positives.
_MIN_QUOTE_CHARS = 40
# A quote is only audited if a citation sits within this many characters — so we
# don't flag legitimate quotes of non-legal text that carry no authority claim.
_AUTHORITY_RADIUS = 280

_QUOTE_RE = re.compile(
    rf'"([^"]{{{_MIN_QUOTE_CHARS},400}})"|“([^”]{{{_MIN_QUOTE_CHARS},400}})”'
)

_FOLD = {
    0x201C: '"',
    0x201D: '"',
    0x2018: "'",
    0x2019: "'",
    0x2013: "-",
    0x2014: "-",
    0x00AB: '"',
    0x00BB: '"',
    0x201E: '"',
}


def _normalise(s: str) -> str:
    """Lowercase, fold smart quotes/dashes, collapse whitespace — for verbatim matching."""
    return re.sub(r"\s+", " ", s.translate(_FOLD).lower()).strip()


def _extract_quotes(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for m in _QUOTE_RE.finditer(text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        out.append((inner, m.start(), m.end()))
    return out


async def attest_response(
    draft_text: str,
    retrieved_ids: list[str],
    audit_quotes: bool = True,
) -> dict[str, Any]:
    """Validate a draft against the retrieved cases — citation existence + verbatim quotes.

    Rail 1 (citation): every citation-shaped string (ECLI, BVerfGE, BGE, US reporter)
    must appear in the citation_strings of `retrieved_ids`.
    Rail 2 (quote, when `audit_quotes`): every quoted span of >=40 chars sitting within
    280 chars of a citation must appear verbatim (normalised) in a retrieved case's
    summary or document text.

    Returns:
        {
            passed: bool,
            violations: [{category, format?, text, span:[s,e], reason}, ...],
            issues_by_category: {citation: [...], quote: [...]},
        }
    """
    violations: list[dict[str, Any]] = []

    # ---- Rail 1: citation existence -------------------------------------------------
    cit_spans = find_citation_spans(draft_text)
    retrieved_citation_texts: set[str] = set()
    summaries: list[str] = []
    doc_texts: list[str] = []
    if retrieved_ids:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT cs.text
                    FROM citation_string cs
                    JOIN case_record c ON c.id = cs.case_id
                    WHERE c.id::text = ANY(%s) OR c.sabin_id = ANY(%s)
                    """,
                    (retrieved_ids, retrieved_ids),
                )
                retrieved_citation_texts = {r[0] for r in await cur.fetchall()}
                if audit_quotes:
                    await cur.execute(
                        "SELECT summary FROM case_record "
                        "WHERE (id::text = ANY(%s) OR sabin_id = ANY(%s)) AND summary IS NOT NULL",
                        (retrieved_ids, retrieved_ids),
                    )
                    summaries = [r[0] for r in await cur.fetchall()]
                    await cur.execute(
                        """
                        SELECT d.text
                        FROM document d
                        JOIN case_record c ON c.id = d.case_id
                        WHERE (c.id::text = ANY(%s) OR c.sabin_id = ANY(%s)) AND d.text IS NOT NULL
                        """,
                        (retrieved_ids, retrieved_ids),
                    )
                    doc_texts = [r[0] for r in await cur.fetchall()]

    for span in cit_spans:
        if any(span.text in cs for cs in retrieved_citation_texts):
            continue
        violations.append(
            {
                "category": "citation",
                "format": span.format_name,
                "text": span.text,
                "span": [span.start, span.end],
                "reason": "citation-shaped string not present in retrieved citation_strings",
            }
        )

    # ---- Rail 2: verbatim quotes ----------------------------------------------------
    if audit_quotes:
        source_pool = _normalise(" \n ".join(summaries + doc_texts))
        for inner, qs, qe in _extract_quotes(draft_text):
            near = any(
                s.start <= qe + _AUTHORITY_RADIUS and s.end >= qs - _AUTHORITY_RADIUS
                for s in cit_spans
            )
            if not near:
                continue
            if source_pool and _normalise(inner) in source_pool:
                continue
            violations.append(
                {
                    "category": "quote",
                    "text": inner,
                    "span": [qs, qe],
                    "reason": "quote not found verbatim in any retrieved source",
                }
            )

    issues_by_category: dict[str, list[dict[str, Any]]] = {"citation": [], "quote": []}
    for v in violations:
        issues_by_category[v["category"]].append(v)

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "issues_by_category": issues_by_category,
    }
