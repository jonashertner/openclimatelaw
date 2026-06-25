import json
import sys
import types
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from ingest.passage_embed import backfill_passage_embeddings
from ingest.passages import content_hash
from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool

_PASSAGES = [
    "The State has a duty of care to protect citizens from dangerous climate change.",
    "Procedural background concerning the admissibility of the claim before this court.",
]


@pytest.fixture
async def case_with_unembedded_passages() -> AsyncGenerator[str]:
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
            for i, t in enumerate(_PASSAGES):
                await cur.execute(
                    """
                    INSERT INTO document_passage
                        (document_id, case_id, para_index, char_start, char_end, text, content_hash)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)
                    """,
                    (doc_id, case_id, i, i * 1000, i * 1000 + len(t), t, content_hash(t)),
                )
        await conn.commit()
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )
        await conn.commit()


def _mock_model(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeST:
        def __init__(self, name: str) -> None:
            self.name = name

        def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
            return np.array([[0.05] * 384 for _ in texts], dtype=float)

    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = FakeST  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)


async def _embedded_count(case_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT count(*) FROM document_passage "
                "WHERE case_id = %s::uuid AND embedding IS NOT NULL",
                (case_id,),
            )
            row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.asyncio
async def test_backfill_passage_embeddings_sets_vectors_and_is_idempotent(
    case_with_unembedded_passages: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_model(monkeypatch)
    case_id = case_with_unembedded_passages
    assert await _embedded_count(case_id) == 0
    r1 = await backfill_passage_embeddings(batch_size=1)
    assert r1["embedded"] >= len(_PASSAGES)
    assert await _embedded_count(case_id) == len(_PASSAGES)
    r2 = await backfill_passage_embeddings()  # nothing left with NULL embedding
    assert r2["embedded"] == 0
