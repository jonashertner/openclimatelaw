import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.documents import get_document_text

_TEXT = "The District Court of The Hague considers the following. " * 20  # ~1140 chars


@pytest.fixture
async def urgenda_doc() -> AsyncGenerator[dict[str, str]]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id::text FROM document WHERE case_id = %s LIMIT 1", (case_id,)
            )
            row = await cur.fetchone()
            assert row is not None
            doc_id = row[0]
            await cur.execute("UPDATE document SET text = %s WHERE id::text = %s", (_TEXT, doc_id))
        await conn.commit()
    yield {"case_id": case_id, "doc_id": doc_id}
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )
        await conn.commit()


@pytest.mark.asyncio
async def test_get_document_text_returns_window_and_citation(urgenda_doc: dict[str, str]) -> None:
    r = await get_document_text(urgenda_doc["doc_id"], offset=0, max_chars=100)
    assert r is not None
    assert r["text"] == _TEXT[:100]
    assert r["returned_chars"] == 100
    assert r["total_chars"] == len(_TEXT)
    assert r["has_more"] is True
    assert r["citation_string"]  # Urgenda carries a citation


@pytest.mark.asyncio
async def test_get_document_text_paginates(urgenda_doc: dict[str, str]) -> None:
    r = await get_document_text(urgenda_doc["doc_id"], offset=100, max_chars=100)
    assert r is not None
    assert r["text"] == _TEXT[100:200]
    assert r["offset"] == 100


@pytest.mark.asyncio
async def test_get_document_text_returns_none_when_not_found() -> None:
    r = await get_document_text("00000000-0000-0000-0000-000000000000")
    assert r is None
