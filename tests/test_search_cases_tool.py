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


# A title-bearing case vs a decoy that only *mentions* the terms densely in its summary.
# Mirrors the live "Urgenda Netherlands" misrank (the title case ranked #3).
_RANK_SEED = [
    # sabin_id, title, summary — the query term "Zephyr" appears once in the TITLE of one
    # case and once in the SUMMARY of the other. Unweighted, fts_rank ties and the
    # canonical_title tiebreak puts "Procedural..." first; title-weighting must flip it.
    (
        "trank-title",
        "Zephyr Holdings Climate Appeal",
        "A routine procedural matter before the court.",
    ),
    (
        "trank-summary",
        "Procedural Matter Appeal",
        "This dispute involves Zephyr Holdings and related corporate entities.",
    ),
]


@pytest.fixture
async def seeded_ranking() -> AsyncGenerator[None]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for sid, title, summary in _RANK_SEED:
                await cur.execute(
                    """
                    INSERT INTO case_record
                        (sabin_id, canonical_title, jurisdiction_code, status_code,
                         primary_source, summary)
                    VALUES (%s, %s, 'US', 'decided', 'sabin', %s)
                    """,
                    (sid, title, summary),
                )
        await conn.commit()
    yield
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = ANY(%s)",
                ([s[0] for s in _RANK_SEED],),
            )
        await conn.commit()


@pytest.mark.asyncio
async def test_title_match_outranks_summary_mention(seeded_ranking: None) -> None:
    result = await search_cases("Zephyr", semantic=False)
    assert result["results"][0]["canonical_title"] == "Zephyr Holdings Climate Appeal"


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


_CRD_DUPE = [
    ("Sabin.zzdupe.0", "Zorgon Climate Coalition v. State", "US", "sabin"),
    (
        "crd:zorgon-climate-coalition",
        "Zorgon Climate Coalition v. the State",
        "US",
        "climate_rights",
    ),
]


@pytest.fixture
async def seeded_crd_dupe() -> AsyncGenerator[None]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for sid, title, juris, src in _CRD_DUPE:
                await cur.execute(
                    "INSERT INTO case_record "
                    "(sabin_id, canonical_title, jurisdiction_code, status_code, primary_source) "
                    "VALUES (%s, %s, %s, 'decided', %s)",
                    (sid, title, juris, src),
                )
        await conn.commit()
    yield
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = ANY(%s)",
                ([s[0] for s in _CRD_DUPE],),
            )
        await conn.commit()


@pytest.mark.asyncio
async def test_search_excludes_climate_rights_stubs(seeded_crd_dupe: None) -> None:
    # The canonical Sabin record must win; the Climate Rights DB stub must not appear.
    r = await search_cases(query="Zorgon Climate Coalition", limit=10, semantic=False)
    ids = [x.get("sabin_id") for x in r["results"]]
    assert "Sabin.zzdupe.0" in ids
    assert "crd:zorgon-climate-coalition" not in ids
