# pyright: basic
"""Pinpoint retrieval over document passages.

find_relevant_passage resolves a claim to the exact passage(s) of a case's
decision text — verbatim text + char offsets + a highlighted snippet + the case
citation — and refuses to guess when nothing clearly matches. get_passage returns
one passage verbatim by (document, index). Lexical FTS works without embeddings;
semantic cosine (when embeddings are present) is additive.
"""

import asyncio
import re
import uuid
from typing import Any

from server.db import get_pool

_STOP = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "or",
    "to",
    "in",
    "for",
    "on",
    "that",
    "this",
    "is",
    "are",
    "be",
    "as",
    "by",
    "with",
    "at",
    "it",
    "its",
    "v",
    "vs",
    "from",
}
_MIN_COVERAGE = 0.4  # refuse to pinpoint below this claim-token coverage (lexical arm)
_VEC_FLOOR = 0.5  # cosine similarity to accept a semantic pinpoint (SQL prefilter == gate)
_LEX_FULL = 0.5  # ts_rank at/above which a lexical match counts as full confidence


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 1 and t not in _STOP}


def _coverage(claim_tokens: set[str], passage: str) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & _tokens(passage)) / len(claim_tokens)


def _confidence(coverage: float, lexical_rank: float, vec_sim: float) -> float:
    """Calibrated [0,1] confidence in a pinpoint match.

    Token *coverage* alone is presence, not quality — a single common claim word found
    in a passage scores coverage 1.0 and used to report confidence 1.0. So: when a
    semantic match clears the floor, use the (well-scaled) cosine; otherwise confidence
    is the WEAKER of coverage and a normalised lexical rank, so an incidental token
    match no longer reads as certainty.
    """
    if vec_sim >= _VEC_FLOOR:
        return round(vec_sim, 3)
    lex_norm = min(1.0, lexical_rank / _LEX_FULL)
    return round(min(coverage, lex_norm), 3)


async def _resolve_case_id(cur: Any, case_id_or_sabin_id: str) -> str | None:
    await cur.execute(
        "SELECT id::text FROM case_record WHERE id::text = %s OR sabin_id = %s",
        (case_id_or_sabin_id, case_id_or_sabin_id),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def _citation_for(cur: Any, case_id: str) -> str | None:
    await cur.execute(
        """
        SELECT text FROM citation_string
        WHERE case_id = %s::uuid
        ORDER BY (lang = 'en') DESC, format
        LIMIT 1
        """,
        (case_id,),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def find_relevant_passage(
    case_id_or_sabin_id: str, claim: str, top_k: int = 5, semantic: bool = True
) -> dict[str, Any]:
    """Resolve a claim to the most relevant verbatim passage(s) of a case's decision text.

    Hybrid: lexical full-text (token coverage) + semantic cosine over per-passage
    embeddings when present. A passage is kept if it clears the lexical floor OR the
    semantic floor, so meaning-based matches surface even without keyword overlap.
    Returns ranked matches with verbatim text, char offsets, a highlighted snippet,
    a confidence score, and the case citation_string — or {no_match: true} when no
    passage clearly matches (do NOT guess a pinpoint in that case).
    """
    top_k = max(1, min(20, int(top_k)))
    claim_tokens = _tokens(claim or "")
    candidate_limit = max(top_k * 5, 25)

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            case_id = await _resolve_case_id(cur, case_id_or_sabin_id)
            if case_id is None:
                return {
                    "case_id": case_id_or_sabin_id,
                    "claim": claim,
                    "count": 0,
                    "no_match": True,
                    "hint": "case not found",
                }
            citation = await _citation_for(cur, case_id)

            # Only embed the claim if this case actually has passage embeddings — avoids
            # paying the model cost (and offloads it from the event loop) when the vector
            # arm cannot contribute.
            qvec: str | None = None
            if semantic and claim:
                await cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM document_passage "
                    "WHERE case_id = %s::uuid AND embedding IS NOT NULL)",
                    (case_id,),
                )
                has_emb = await cur.fetchone()
                if has_emb and has_emb[0]:
                    from server.tools.search import _embed_query

                    vec = await asyncio.to_thread(_embed_query, claim)
                    if vec is not None:
                        qvec = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"

            await cur.execute(
                """
                WITH q AS (SELECT plainto_tsquery('simple', %(claim)s) AS tsq)
                SELECT
                    p.document_id::text,
                    p.para_index,
                    p.char_start,
                    p.char_end,
                    p.text,
                    ts_rank(to_tsvector('simple', p.text), (SELECT tsq FROM q)) AS lex_rank,
                    CASE WHEN %(qvec)s::text IS NULL OR p.embedding IS NULL THEN NULL
                         ELSE 1 - (p.embedding <=> %(qvec)s::vector) END AS vec_sim,
                    ts_headline(
                        'simple', p.text, (SELECT tsq FROM q),
                        'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=24'
                    ) AS snippet
                FROM document_passage p, q
                WHERE p.case_id = %(case_id)s::uuid
                  AND (
                    to_tsvector('simple', p.text) @@ (SELECT tsq FROM q)
                    OR (
                        %(qvec)s::text IS NOT NULL AND p.embedding IS NOT NULL
                        AND 1 - (p.embedding <=> %(qvec)s::vector) >= %(vfloor)s
                    )
                  )
                ORDER BY GREATEST(
                    ts_rank(to_tsvector('simple', p.text), (SELECT tsq FROM q)) * 10.0,
                    CASE WHEN %(qvec)s::text IS NULL OR p.embedding IS NULL THEN 0
                         ELSE 1 - (p.embedding <=> %(qvec)s::vector) END
                ) DESC
                LIMIT %(cand)s
                """,
                {
                    "claim": claim,
                    "case_id": case_id,
                    "cand": candidate_limit,
                    "qvec": qvec,
                    "vfloor": _VEC_FLOOR,
                },
            )
            rows = await cur.fetchall()

    matches = []
    for r in rows:
        coverage = _coverage(claim_tokens, r[4])
        vec_sim = float(r[6]) if r[6] is not None else 0.0
        lexrank = float(r[5]) if r[5] is not None else 0.0
        if coverage < _MIN_COVERAGE and vec_sim < _VEC_FLOOR:
            continue
        matches.append(
            {
                "document_id": r[0],
                "para_index": r[1],
                "char_start": r[2],
                "char_end": r[3],
                "text": r[4],
                "lexical_rank": lexrank,
                "semantic_similarity": round(vec_sim, 3),
                "confidence": _confidence(coverage, lexrank, vec_sim),
                "highlighted_snippet": r[7],
                "citation_string": citation,
            }
        )

    matches = matches[:top_k]
    if not matches:
        return {
            "case_id": case_id,
            "claim": claim,
            "count": 0,
            "no_match": True,
            "hint": "no passage clearly matches this claim — do not guess a pinpoint",
        }
    return {"case_id": case_id, "claim": claim, "count": len(matches), "matches": matches}


async def get_passage(document_id: str, para_index: int) -> dict[str, Any] | None:
    """Return one passage verbatim by (document_id, para_index), with neighbours + citation."""
    try:
        uuid.UUID(str(document_id))
    except ValueError, AttributeError, TypeError:
        return None  # non-UUID id (e.g. a sabin_id) → not found, never a raw DB error
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT case_id::text, char_start, char_end, text
                FROM document_passage
                WHERE document_id = %s::uuid AND para_index = %s
                """,
                (document_id, para_index),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            case_id, char_start, char_end, text = row
            await cur.execute(
                """
                SELECT max(para_index) FILTER (WHERE para_index < %(p)s),
                       min(para_index) FILTER (WHERE para_index > %(p)s)
                FROM document_passage WHERE document_id = %(d)s::uuid
                """,
                {"p": para_index, "d": document_id},
            )
            nb = await cur.fetchone()
            citation = await _citation_for(cur, case_id)

    return {
        "document_id": document_id,
        "case_id": case_id,
        "para_index": para_index,
        "char_start": char_start,
        "char_end": char_end,
        "text": text,
        "prev_index": nb[0] if nb else None,
        "next_index": nb[1] if nb else None,
        "citation_string": citation,
    }
