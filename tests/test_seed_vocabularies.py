import pytest

from server.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_minimum_vocabularies_seeded():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT code FROM vocabulary_jurisdiction WHERE code = 'NL'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT id FROM vocabulary_court WHERE id = 'nl-hoge-raad'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_status WHERE code = 'decided'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_outcome WHERE code = 'plaintiff_won'"
            )
            assert (await cur.fetchone()) is not None

            await cur.execute(
                "SELECT code FROM vocabulary_claim_type "
                "WHERE code IN ('human_rights', 'constitutional', 'tort') "
                "ORDER BY code"
            )
            rows = await cur.fetchall()
            assert [r[0] for r in rows] == ["constitutional", "human_rights", "tort"]

            await cur.execute(
                "SELECT code FROM vocabulary_document_category WHERE code = 'opinion'"
            )
            assert (await cur.fetchone()) is not None
    await close_pool()
