from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastmcp import Client

from server.db import get_pool
from server.main import build_mcp
from server.tools.search import search_cases

# (sabin_id, canonical_title, jurisdiction, status, filing_date, decision_date)
_SEED = [
    ("tsearch-alpha", "Climate Alpha v. State", "US", "decided", "2019-01-01", "2020-01-01"),
    ("tsearch-bravo", "Climate Bravo v. State", "US", "decided", "2023-01-01", "2024-06-15"),
    ("tsearch-charlie", "Climate Charlie v. State", "US", "decided", "2025-01-01", "2026-03-01"),
]


@pytest.fixture
async def seeded_cases() -> AsyncGenerator[None]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for sid, title, juris, status, filed, decided in _SEED:
                await cur.execute(
                    """
                    INSERT INTO case_record
                        (sabin_id, canonical_title, jurisdiction_code, status_code,
                         primary_source, filing_date, decision_date)
                    VALUES (%s, %s, %s, %s, 'sabin', %s::date, %s::date)
                    """,
                    (sid, title, juris, status, filed, decided),
                )
        await conn.commit()
    yield
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = ANY(%s)",
                ([s[0] for s in _SEED],),
            )
        await conn.commit()


def _titles(result: dict[str, Any]) -> list[str]:
    return [r["canonical_title"] for r in result["results"]]


@pytest.mark.asyncio
async def test_results_include_filing_and_decision_dates(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False)
    assert result["count"] == 3
    by_title = {r["canonical_title"]: r for r in result["results"]}
    charlie = by_title["Climate Charlie v. State"]
    assert charlie["decision_date"] == "2026-03-01"
    assert charlie["filing_date"] == "2025-01-01"


@pytest.mark.asyncio
async def test_decided_after_filters_by_decision_date(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, decided_after="2024-01-01")
    assert set(_titles(result)) == {"Climate Bravo v. State", "Climate Charlie v. State"}


@pytest.mark.asyncio
async def test_decided_before_filters_by_decision_date(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, decided_before="2024-12-31")
    assert set(_titles(result)) == {"Climate Alpha v. State", "Climate Bravo v. State"}


@pytest.mark.asyncio
async def test_filed_after_filters_by_filing_date(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, filed_after="2024-01-01")
    assert set(_titles(result)) == {"Climate Charlie v. State"}


@pytest.mark.asyncio
async def test_sort_newest_orders_by_decision_date_desc(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, sort="newest")
    assert _titles(result) == [
        "Climate Charlie v. State",
        "Climate Bravo v. State",
        "Climate Alpha v. State",
    ]


@pytest.mark.asyncio
async def test_sort_oldest_orders_by_decision_date_asc(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, sort="oldest")
    assert _titles(result) == [
        "Climate Alpha v. State",
        "Climate Bravo v. State",
        "Climate Charlie v. State",
    ]


@pytest.mark.asyncio
async def test_browse_without_query_returns_date_sorted(seeded_cases: None) -> None:
    # No keyword: browse the corpus newest-first.
    result = await search_cases("", semantic=False, sort="newest")
    assert _titles(result) == [
        "Climate Charlie v. State",
        "Climate Bravo v. State",
        "Climate Alpha v. State",
    ]


@pytest.mark.asyncio
async def test_browse_with_date_filter_no_keyword(seeded_cases: None) -> None:
    result = await search_cases("", semantic=False, decided_after="2024-01-01", sort="oldest")
    assert _titles(result) == ["Climate Bravo v. State", "Climate Charlie v. State"]


@pytest.mark.asyncio
async def test_invalid_sort_raises() -> None:
    with pytest.raises(ValueError, match="invalid sort"):
        await search_cases("Climate", semantic=False, sort="bogus")


@pytest.mark.asyncio
async def test_empty_query_without_sort_or_filter_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        await search_cases("", semantic=False)


@pytest.mark.asyncio
async def test_total_is_full_match_count_independent_of_limit(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, limit=2, sort="newest")
    assert result["count"] == 2
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_offset_paginates_results(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, sort="newest", limit=1, offset=1)
    assert _titles(result) == ["Climate Bravo v. State"]
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_match_snippet_highlights_query_term(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False)
    assert result["count"] == 3
    for r in result["results"]:
        assert r["match_snippet"] is not None
        assert "climate" in r["match_snippet"].lower()


@pytest.mark.asyncio
async def test_browse_has_no_match_snippet(seeded_cases: None) -> None:
    result = await search_cases("", semantic=False, sort="newest")
    assert all(r["match_snippet"] is None for r in result["results"])


@pytest.mark.asyncio
async def test_jurisdiction_filter_is_case_insensitive(seeded_cases: None) -> None:
    result = await search_cases("Climate", semantic=False, jurisdiction="us")
    assert result["count"] == 3


@pytest.mark.asyncio
async def test_invalid_date_raises_clean_error() -> None:
    with pytest.raises(ValueError, match="decided_after"):
        await search_cases("Climate", semantic=False, decided_after="not-a-date")


@pytest.mark.asyncio
async def test_tool_schema_exposes_date_and_sort_params() -> None:
    mcp = build_mcp()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        search = next(t for t in tools if t.name == "search_cases")
        props = search.inputSchema["properties"]
        for p in ("decided_after", "decided_before", "filed_after", "filed_before", "sort"):
            assert p in props, f"missing param {p}"
