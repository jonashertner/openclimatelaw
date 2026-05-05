import pytest
from fastmcp import Client

from server.main import build_mcp
from server.tools.statistics import get_statistics


@pytest.mark.asyncio
async def test_statistics_empty_database_returns_zeros():
    result = await get_statistics(scope="all", group_by=None)
    assert result["scope"] == "all"
    assert result["totals"]["case_count"] == 0
    assert result["totals"]["document_count"] == 0
    assert result["totals"]["statute_count"] == 0
    assert result["totals"]["jurisdiction_count"] == 0
    assert result["last_refresh_at"] is None


@pytest.mark.asyncio
async def test_statistics_group_by_jurisdiction_returns_empty_list_when_no_data():
    result = await get_statistics(scope="all", group_by="jurisdiction")
    assert result["groups"] == []


@pytest.mark.asyncio
async def test_statistics_invalid_scope_raises():
    with pytest.raises(ValueError, match="invalid scope"):
        await get_statistics(scope="bogus", group_by=None)


@pytest.mark.asyncio
async def test_statistics_invalid_group_by_raises():
    with pytest.raises(ValueError, match="invalid group_by"):
        await get_statistics(scope="all", group_by="bogus")


@pytest.mark.asyncio
async def test_get_statistics_via_fastmcp_client():
    mcp = build_mcp()
    async with Client(mcp) as client:
        # tools/list should include get_statistics
        tools = await client.list_tools()
        assert any(t.name == "get_statistics" for t in tools)

        # tools/call should return a structured payload with totals
        result = await client.call_tool("get_statistics", {"scope": "all"})
        # FastMCP's CallToolResult exposes structured_content for tools returning dicts
        assert result.structured_content is not None
        assert result.structured_content["totals"]["case_count"] == 0
        assert result.structured_content["scope"] == "all"
