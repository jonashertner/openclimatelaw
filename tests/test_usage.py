import pytest
from fastmcp import Client, FastMCP

from server.db import get_pool
from server.usage import UsageMiddleware, hash_ip


def test_hash_ip_is_deterministic_pseudonymous() -> None:
    h1 = hash_ip("203.0.113.5")
    h2 = hash_ip("203.0.113.5")
    assert h1 == h2 and h1  # deterministic, non-empty
    assert h1 != "203.0.113.5"  # not the raw IP
    assert hash_ip("203.0.113.6") != h1  # distinct IPs → distinct hashes
    assert hash_ip(None) is None and hash_ip("") is None


@pytest.mark.asyncio
async def test_tool_call_writes_usage_event() -> None:
    mcp = FastMCP(name="usage-test")

    @mcp.tool
    async def usage_probe(x: str) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"echo": x}

    mcp.add_middleware(UsageMiddleware())

    try:
        async with Client(mcp) as c:
            await c.call_tool("usage_probe", {"x": "hello"})
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT tool, ok, client_name, arguments FROM usage_event "
                    "WHERE tool = 'usage_probe'"
                )
                row = await cur.fetchone()
        assert row is not None
        assert row[0] == "usage_probe" and row[1] is True
        # full logging (default): the arguments are captured
        assert row[3] == {"x": "hello"}
    finally:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM usage_event WHERE tool = 'usage_probe'")
            await conn.commit()
