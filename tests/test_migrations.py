import pytest

from server.db import close_pool, get_pool


@pytest.mark.asyncio
async def test_vocabulary_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('vocabulary_jurisdiction', 'vocabulary_court',
                                     'vocabulary_claim_type', 'vocabulary_status',
                                     'vocabulary_outcome', 'vocabulary_document_category')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == [
                "vocabulary_claim_type",
                "vocabulary_court",
                "vocabulary_document_category",
                "vocabulary_jurisdiction",
                "vocabulary_outcome",
                "vocabulary_status",
            ]
    await close_pool()


@pytest.mark.asyncio
async def test_case_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('case_record', 'case_party', 'case_claim_type',
                                     'citation_string')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == [
                "case_claim_type",
                "case_party",
                "case_record",
                "citation_string",
            ]
    await close_pool()


@pytest.mark.asyncio
async def test_document_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'document'
                ORDER BY column_name
                """
            )
            rows = await cur.fetchall()
            names = {r[0] for r in rows}
            for required in [
                "id",
                "case_id",
                "category_code",
                "title",
                "filed_date",
                "filed_by",
                "upstream_url",
                "storage_url",
                "text",
                "text_lang",
                "text_extraction_method",
                "text_translation_en",
                "provenance",
                "created_at",
            ]:
                assert required in names, f"missing column: {required}"
    await close_pool()


@pytest.mark.asyncio
async def test_statute_tables_exist():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('statute', 'case_statute')
                ORDER BY table_name
                """
            )
            rows = await cur.fetchall()
            names = [r[0] for r in rows]
            assert names == ["case_statute", "statute"]
    await close_pool()


@pytest.mark.asyncio
async def test_citation_edge_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'citation_edge'
                """
            )
            row = await cur.fetchone()
            assert row is not None
    await close_pool()


@pytest.mark.asyncio
async def test_merge_candidate_table_exists():
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'merge_candidate'
                """
            )
            row = await cur.fetchone()
            assert row is not None
    await close_pool()
