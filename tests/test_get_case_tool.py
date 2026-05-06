import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.cases import get_case


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="fixture",
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    # Cleanup: delete the Urgenda case so other tests see an empty DB
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_get_case_by_uuid(upserted_urgenda_id: str) -> None:
    result = await get_case(upserted_urgenda_id)
    assert result is not None
    assert "Urgenda" in result["canonical_title"]
    assert result["jurisdiction_code"] == "NL"
    assert len(result["parties"]) == 3
    assert sorted(result["claim_types"]) == ["constitutional", "human_rights", "tort"]
    assert len(result["documents"]) == 3
    assert len(result["citation_strings"]) == 2
    assert "provenance" in result


@pytest.mark.asyncio
async def test_get_case_by_sabin_id(upserted_urgenda_id: str) -> None:
    result = await get_case("urgenda-foundation-v-state-of-the-netherlands")
    assert result is not None
    assert "Urgenda" in result["canonical_title"]
    assert result["id"] == upserted_urgenda_id


@pytest.mark.asyncio
async def test_get_case_returns_none_when_not_found() -> None:
    result = await get_case("nonexistent-id")
    assert result is None
