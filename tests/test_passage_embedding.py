# pyright: reportPrivateUsage=false
import pytest

from server.tools.passages import _VEC_FLOOR, _confidence


def test_vec_floor_recalibrated_for_e5() -> None:
    # e5-small cosines run high; the accept floor was raised from 0.5 (all-MiniLM) to 0.80.
    assert _VEC_FLOOR == 0.80


def test_confidence_reports_cosine_above_floor() -> None:
    # a semantic match clearing the e5 floor → report the cosine as confidence
    assert _confidence(coverage=0.0, lexical_rank=0.0, vec_sim=0.82) == 0.82
    # e5 sim below the floor → fall back to the weaker of coverage / normalised lexical rank
    assert _confidence(coverage=0.5, lexical_rank=0.5, vec_sim=0.60) == 0.5


@pytest.mark.asyncio
async def test_backfill_passages_embeds_new_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    # embed-on-ingest: running the passage backfill on a fresh doc must ALSO populate
    # passage_embedding for the new content_hashes (so a new case gets semantic pinpoint).
    import server.embed as embed_mod
    from ingest.passages import backfill_passages
    from server.db import get_pool

    # deterministic embedder — avoid loading the real model in the unit test
    def _fake(texts: list[str]) -> list[list[float]]:
        return [[0.03] * 384 for _ in texts]

    monkeypatch.setattr(embed_mod, "embed_passages", _fake)

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO case_record (sabin_id, canonical_title, jurisdiction_code, "
                "status_code, primary_source) VALUES ('tpe-1','Embed OnIngest v. X','US',"
                "'decided','sabin') RETURNING id::text"
            )
            row = await cur.fetchone()
            assert row is not None
            cid = row[0]
            await cur.execute(
                "INSERT INTO document (case_id, category_code, title, upstream_url, text) VALUES "
                "(%s::uuid,'opinion','Op','https://example.org/tpe-1','The State owes a duty of "
                "care to reduce emissions and must act to protect a stable climate system for "
                "its citizens.') RETURNING id::text",
                (cid,),
            )
            drow = await cur.fetchone()
            assert drow is not None
        await conn.commit()

    try:
        res = await backfill_passages(only_missing=True, embed=True)
        assert res["passages"] >= 1
        assert res["embedded"] >= 1
        # the new passages actually have embeddings joinable by content_hash
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT count(*) FROM document_passage p "
                    "JOIN passage_embedding pe ON pe.content_hash = p.content_hash "
                    "WHERE p.case_id = %s::uuid",
                    (cid,),
                )
                nrow = await cur.fetchone()
        assert nrow is not None and nrow[0] >= 1
    finally:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM passage_embedding WHERE content_hash IN "
                    "(SELECT content_hash FROM document_passage p JOIN case_record c "
                    "ON c.id = p.case_id WHERE c.sabin_id = 'tpe-1')"
                )
                await cur.execute("DELETE FROM case_record WHERE sabin_id = 'tpe-1'")
            await conn.commit()
