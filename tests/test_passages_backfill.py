import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.passages import backfill_passages
from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool

_DOC_TEXT = (
    "The State has a duty of care to protect citizens from climate change.\n\n"
    "x\n\n"
    "The court allocated the costs of the proceedings to the State as the losing party."
)


@pytest.fixture
async def doc_with_text() -> AsyncGenerator[str]:
    pool = await get_pool()
    parsed = parse_sabin_record(
        SabinCaseRecord.model_validate(
            json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
        ),
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="fixture",
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
            await cur.execute(
                "UPDATE document SET text = %s WHERE id::text = %s", (_DOC_TEXT, doc_id)
            )
        await conn.commit()
    yield doc_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )
        await conn.commit()


async def _passage_count(doc_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(*) FROM document_passage WHERE document_id = %s::uuid", (doc_id,)
            )
            row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.asyncio
async def test_backfill_creates_passages_and_is_idempotent(doc_with_text: str) -> None:
    r1 = await backfill_passages()
    assert r1["passages"] >= 1
    # the tiny "x" paragraph is dropped; the two real paragraphs are kept
    assert await _passage_count(doc_with_text) == 2
    r2 = await backfill_passages()  # idempotent: only_missing skips already-populated docs
    assert await _passage_count(doc_with_text) == 2
    assert r2["documents"] == 0
