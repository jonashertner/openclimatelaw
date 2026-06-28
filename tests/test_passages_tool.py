import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.passages import content_hash
from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.passages import find_relevant_passage, get_passage

_PASSAGES = [
    "The State has a duty of care to protect its citizens from dangerous climate "
    "change and must reduce greenhouse gas emissions accordingly.",
    "Procedural background concerning the admissibility of the claim and the "
    "standing of the foundation to bring the action before this court.",
    "The court considered the costs of the proceedings and allocated them to "
    "the State as the unsuccessful party in this matter.",
]


@pytest.fixture
async def case_with_passages() -> AsyncGenerator[dict[str, str]]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    parsed = parse_sabin_record(
        SabinCaseRecord.model_validate(fixture),
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
    yield {"case_id": case_id, "doc_id": doc_id}
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )
        await conn.commit()


@pytest.mark.asyncio
async def test_find_relevant_passage_pinpoints_matching_paragraph(
    case_with_passages: dict[str, str],
) -> None:
    r = await find_relevant_passage(
        case_with_passages["case_id"], "duty of care to reduce emissions", semantic=False
    )
    assert r["count"] >= 1
    top = r["matches"][0]
    assert top["text"] == _PASSAGES[0]
    assert "duty of care" in top["text"]
    assert top["citation_string"]
    assert "<mark>" in top["highlighted_snippet"]


@pytest.mark.asyncio
async def test_find_relevant_passage_refuses_when_no_match(
    case_with_passages: dict[str, str],
) -> None:
    r = await find_relevant_passage(
        case_with_passages["case_id"], "trademark patent royalties licensing", semantic=False
    )
    assert r["count"] == 0
    assert r["no_match"] is True


@pytest.mark.asyncio
async def test_find_relevant_passage_semantic_arm(
    case_with_passages: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Give passage 0 a known embedding and mock the query embedder to match it; a claim
    # with NO lexical overlap must still surface passage 0 via the semantic arm.
    import server.tools.search as search

    vec = [0.05] * 384
    lit = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE document_passage SET embedding = %s::vector "
                "WHERE case_id = %s::uuid AND para_index = 0",
                (lit, case_with_passages["case_id"]),
            )
        await conn.commit()

    def _fake_embed(_text: str) -> list[float]:
        return vec

    monkeypatch.setattr(search, "_embed_query", _fake_embed)

    r = await find_relevant_passage(
        case_with_passages["case_id"], "wholly unrelated lexical tokens zzz qqq", semantic=True
    )
    assert r["count"] >= 1
    assert any(m["para_index"] == 0 and m["semantic_similarity"] >= 0.5 for m in r["matches"])


@pytest.mark.asyncio
async def test_get_passage_returns_verbatim_with_neighbours(
    case_with_passages: dict[str, str],
) -> None:
    r = await get_passage(case_with_passages["doc_id"], 0)
    assert r is not None
    assert r["text"] == _PASSAGES[0]
    assert r["prev_index"] is None
    assert r["next_index"] == 1
    assert r["citation_string"]


@pytest.mark.asyncio
async def test_get_passage_not_found() -> None:
    r = await get_passage("00000000-0000-0000-0000-000000000000", 0)
    assert r is None


@pytest.mark.asyncio
async def test_get_passage_non_uuid_returns_none() -> None:
    # A non-UUID id (e.g. a sabin_id copied in by mistake) must return None, not a raw DB error.
    assert await get_passage("Sabin.family.2823.0", 0) is None
    assert await get_passage("not-a-uuid", 0) is None
