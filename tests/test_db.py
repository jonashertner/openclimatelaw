import pytest

from server.db import get_pool


@pytest.mark.asyncio
async def test_pool_executes_select_one():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 AS n")
            row = await cur.fetchone()
            assert row == (1,)
    await pool.close()
