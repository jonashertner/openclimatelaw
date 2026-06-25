# pyright: basic
"""search_cases — hybrid full-text + trigram + vector semantic search.

The major usability gap before this tool: LLMs could only retrieve cases by
sabin_id (e.g. Sabin.family.9998.0) or canonical UUID. Without knowing those,
'find Urgenda v. Netherlands' had no way to land on the right record. Now an
LLM can call search_cases('Urgenda Netherlands') and get back ranked matches.

Hybrid scoring (each row gets the max of the three):
- FTS rank — Postgres `to_tsvector` + `plainto_tsquery` for tokenized matching.
  Catches topic searches: 'youth plaintiffs', 'Amazon deforestation'.
- Trigram similarity — pg_trgm `similarity(canonical_title, query)`. Catches
  typos and partial case names: 'klimasenoirinnen' -> KlimaSeniorinnen.
- Vector similarity — cosine distance on sentence-transformer embeddings, for
  conceptual matches even when no keyword overlaps.

The final rank is `GREATEST(fts_rank * 10, trigram_sim, vector_sim)`.

Beyond keyword relevance the tool supports faceted filters (jurisdiction,
claim_type, status), inclusive date ranges (decided_*/filed_*), recency sorting
('newest'/'oldest'), keyword-less date browsing (empty query), pagination
(limit + offset with a `total` match count), and highlighted match snippets.

Every result carries the canonical citation_string so the LLM has a verbatim
citation to use immediately — closing the loop with the R1 contract.
"""

import threading
from datetime import date as _date
from typing import Any, LiteralString

from server.db import get_pool

_QUERY_EMBEDDER = None  # lazily loaded SentenceTransformer
_EMBEDDER_LOCK = threading.Lock()

_VALID_SORTS = ("relevance", "newest", "oldest")

# Allowlisted ORDER BY clauses. Declared LiteralString so the assembled SQL
# stays a LiteralString (psycopg's typed execute rejects a runtime str) — never
# interpolate untrusted text here; `sort` is validated against _VALID_SORTS.
_ORDER_BY: dict[str, LiteralString] = {
    "relevance": "rank DESC, canonical_title",
    "newest": "decision_date DESC NULLS LAST, filing_date DESC NULLS LAST, canonical_title",
    "oldest": "decision_date ASC NULLS LAST, filing_date ASC NULLS LAST, canonical_title",
}


def _embed_query(text: str) -> list[float] | None:
    """Encode the query into a 384-dim vector. Returns None if model unavailable."""
    global _QUERY_EMBEDDER
    try:
        if _QUERY_EMBEDDER is None:
            # Double-checked lock: a startup warm thread and a request may race.
            with _EMBEDDER_LOCK:
                if _QUERY_EMBEDDER is None:
                    from sentence_transformers import SentenceTransformer

                    _QUERY_EMBEDDER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        emb = _QUERY_EMBEDDER.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in emb]
    except Exception:
        return None


def warm_embedder() -> bool:
    """Eagerly load the embedding model so the first real query doesn't pay the
    cold-load latency. Called at server startup. Returns True if the model loaded."""
    _embed_query("warmup")
    return _QUERY_EMBEDDER is not None


def _validate_iso_date(name: str, value: str | None) -> None:
    """Raise a clear ValueError if `value` is set but not an ISO 'YYYY-MM-DD' date."""
    if value is None:
        return
    try:
        _date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"invalid {name}: {value!r}; expected ISO date 'YYYY-MM-DD'") from None


# Everything up to (and including) the ORDER BY keyword. The ORDER BY clause and
# the LIMIT/OFFSET tail are concatenated from LiteralStrings so the whole
# statement remains a LiteralString for psycopg's typed execute.
_SEARCH_SQL_HEAD: LiteralString = """
                WITH q AS (
                    SELECT
                        plainto_tsquery('simple', %(query)s) AS tsq,
                        %(query)s AS qstr
                )
                SELECT * FROM (
                    SELECT
                        c.id::text,
                        c.sabin_id,
                        c.canonical_title,
                        c.jurisdiction_code,
                        c.court_id,
                        c.status_code,
                        c.outcome_code,
                        c.filing_date,
                        c.decision_date,
                        substring(c.summary FROM 1 FOR 240) AS summary_excerpt,
                        CASE
                            WHEN %(browse)s::boolean THEN NULL
                            ELSE ts_headline(
                                'simple',
                                c.canonical_title || ' ' || coalesce(c.summary, ''),
                                (SELECT tsq FROM q),
                                'StartSel=<b>, StopSel=</b>, MaxFragments=2, MaxWords=18'
                            )
                        END AS match_snippet,
                        (
                            SELECT text FROM citation_string
                            WHERE case_id = c.id AND lang = 'en'
                            ORDER BY format LIMIT 1
                        ) AS citation_string,
                        ts_rank(
                            '{0.1, 0.2, 0.4, 1.0}',
                            setweight(to_tsvector('simple', c.canonical_title), 'A')
                            || setweight(to_tsvector('simple', coalesce(c.summary, '')), 'D'),
                            (SELECT tsq FROM q)
                        ) AS fts_rank,
                        similarity(c.canonical_title, (SELECT qstr FROM q)) AS trgm_sim,
                        CASE WHEN %(qvec)s::text IS NULL OR c.embedding IS NULL
                             THEN NULL
                             ELSE 1 - (c.embedding <=> %(qvec)s::vector)
                        END AS vector_sim,
                        GREATEST(
                            ts_rank(
                                '{0.1, 0.2, 0.4, 1.0}',
                                setweight(to_tsvector('simple', c.canonical_title), 'A')
                                || setweight(to_tsvector('simple', coalesce(c.summary, '')), 'D'),
                                (SELECT tsq FROM q)
                            ) * 10.0,
                            similarity(c.canonical_title, (SELECT qstr FROM q)),
                            CASE WHEN %(qvec)s::text IS NULL OR c.embedding IS NULL
                                 THEN 0
                                 ELSE 1 - (c.embedding <=> %(qvec)s::vector)
                            END
                        ) AS rank,
                        count(*) OVER() AS total_count
                    FROM case_record c, q
                    WHERE
                        (
                            %(browse)s::boolean
                            OR (
                                setweight(to_tsvector('simple', c.canonical_title), 'A')
                                || setweight(to_tsvector('simple', coalesce(c.summary, '')), 'D')
                            ) @@ q.tsq
                            OR similarity(c.canonical_title, q.qstr) > 0.2
                            OR (
                                %(qvec)s::text IS NOT NULL AND c.embedding IS NOT NULL
                                AND (1 - (c.embedding <=> %(qvec)s::vector)) > 0.4
                            )
                        )
                        AND (
                            %(jurisdiction)s::text IS NULL
                            OR c.jurisdiction_code = %(jurisdiction)s::text
                        )
                        AND (%(status)s::text IS NULL OR c.status_code = %(status)s::text)
                        AND (
                            %(claim_type)s::text IS NULL
                            OR EXISTS (
                                SELECT 1 FROM case_claim_type cct
                                WHERE cct.case_id = c.id
                                  AND cct.claim_type_code = %(claim_type)s::text
                            )
                        )
                        AND (
                            %(decided_after)s::date IS NULL
                            OR c.decision_date >= %(decided_after)s::date
                        )
                        AND (
                            %(decided_before)s::date IS NULL
                            OR c.decision_date <= %(decided_before)s::date
                        )
                        AND (
                            %(filed_after)s::date IS NULL
                            OR c.filing_date >= %(filed_after)s::date
                        )
                        AND (
                            %(filed_before)s::date IS NULL
                            OR c.filing_date <= %(filed_before)s::date
                        )
                ) ranked
                ORDER BY """

_SEARCH_SQL_TAIL: LiteralString = """
                LIMIT %(limit)s OFFSET %(offset)s
            """


async def search_cases(
    query: str,
    jurisdiction: str | None = None,
    claim_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    semantic: bool = True,
    decided_after: str | None = None,
    decided_before: str | None = None,
    filed_after: str | None = None,
    filed_before: str | None = None,
    sort: str = "relevance",
) -> dict[str, Any]:
    """Hybrid search (FTS + trigram + optional vector) with filters, dates, sort.

    sort: 'relevance' (default) | 'newest' | 'oldest' — newest/oldest order by
    decision_date, falling back to filing_date. Date bounds (ISO 'YYYY-MM-DD')
    are inclusive. Pass an empty query to browse the corpus by date; this
    requires a non-relevance sort or at least one filter. Returns the page of
    results plus `total` (full match count) for pagination via limit + offset.
    """
    if sort not in _VALID_SORTS:
        raise ValueError(f"invalid sort: {sort!r}; expected one of {list(_VALID_SORTS)}")

    _validate_iso_date("decided_after", decided_after)
    _validate_iso_date("decided_before", decided_before)
    _validate_iso_date("filed_after", filed_after)
    _validate_iso_date("filed_before", filed_before)

    # Jurisdiction codes are stored upper-case ISO alpha-2 / body codes — accept
    # any casing from callers.
    if jurisdiction is not None:
        jurisdiction = jurisdiction.strip().upper() or None

    query = query.strip() if query else ""
    browse = query == ""
    has_filter = any(
        x is not None
        for x in (
            jurisdiction,
            claim_type,
            status,
            decided_after,
            decided_before,
            filed_after,
            filed_before,
        )
    )
    if browse and sort == "relevance" and not has_filter:
        raise ValueError("query must be non-empty unless a sort or filter is provided")

    # No relevance signal without a query — browse newest-first by default.
    effective_sort = "newest" if (browse and sort == "relevance") else sort
    limit = max(1, min(50, int(limit)))
    offset = max(0, int(offset))

    # Encode query for vector search; fall back gracefully if model unavailable.
    qvec_literal: str | None = None
    if semantic and not browse:
        qvec = _embed_query(query)
        if qvec is not None:
            qvec_literal = "[" + ",".join(f"{v:.7f}" for v in qvec) + "]"

    sql: LiteralString = _SEARCH_SQL_HEAD + _ORDER_BY[effective_sort] + _SEARCH_SQL_TAIL

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                sql,
                {
                    "query": query,
                    "qvec": qvec_literal,
                    "browse": browse,
                    "jurisdiction": jurisdiction,
                    "claim_type": claim_type,
                    "status": status,
                    "decided_after": decided_after,
                    "decided_before": decided_before,
                    "filed_after": filed_after,
                    "filed_before": filed_before,
                    "limit": limit,
                    "offset": offset,
                },
            )
            rows = await cur.fetchall()

    results = [
        {
            "id": r[0],
            "sabin_id": r[1],
            "canonical_title": r[2],
            "jurisdiction_code": r[3],
            "court_id": r[4],
            "status_code": r[5],
            "outcome_code": r[6],
            "filing_date": r[7].isoformat() if r[7] else None,
            "decision_date": r[8].isoformat() if r[8] else None,
            "summary_excerpt": r[9],
            "match_snippet": r[10],
            "citation_string": r[11],
            "fts_rank": float(r[12]) if r[12] is not None else 0.0,
            "trigram_sim": float(r[13]) if r[13] is not None else 0.0,
            "vector_sim": float(r[14]) if r[14] is not None else None,
            "rank": float(r[15]) if r[15] is not None else 0.0,
        }
        for r in rows
    ]

    total = int(rows[0][16]) if rows else 0

    return {
        "query": query,
        "filters": {
            "jurisdiction": jurisdiction,
            "claim_type": claim_type,
            "status": status,
            "decided_after": decided_after,
            "decided_before": decided_before,
            "filed_after": filed_after,
            "filed_before": filed_before,
        },
        "sort": effective_sort,
        "total": total,
        "count": len(results),
        "limit": limit,
        "offset": offset,
        "results": results,
    }
