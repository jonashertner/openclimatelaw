from typing import Any, Literal

from server.db import get_pool

Scope = Literal["all", "sabin"]
GroupBy = Literal["jurisdiction", "claim_type", "year", "status", "outcome"]

VALID_SCOPES = {"all", "sabin"}
VALID_GROUP_BY = {"jurisdiction", "claim_type", "year", "status", "outcome"}


async def get_statistics(
    scope: Scope = "all",
    group_by: GroupBy | None = None,
) -> dict[str, Any]:
    """Return structured statistics over the corpus.

    Args:
        scope: 'all' | 'sabin'.
        group_by: when provided, returns per-group counts in addition to totals.

    Returns:
        A dict with `scope`, `totals`, optional `groups`, and `last_refresh_at`.
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"invalid scope: {scope!r} (must be one of {sorted(VALID_SCOPES)})")
    if group_by is not None and group_by not in VALID_GROUP_BY:
        raise ValueError(
            f"invalid group_by: {group_by!r} (must be one of {sorted(VALID_GROUP_BY)})"
        )

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            scope_filter = ""
            if scope == "sabin":
                scope_filter = "WHERE primary_source = 'sabin'"

            await cur.execute(f"SELECT count(*) FROM case_record {scope_filter}")
            (case_count,) = await cur.fetchone()  # type: ignore[misc]

            await cur.execute(
                f"""
                SELECT count(*) FROM document d
                {("JOIN case_record c ON c.id = d.case_id " + scope_filter) if scope_filter else ""}
                """
            )
            (document_count,) = await cur.fetchone()  # type: ignore[misc]

            statute_count = 0
            if scope == "all":
                await cur.execute("SELECT count(*) FROM statute")
                (statute_count,) = await cur.fetchone()  # type: ignore[misc]

            await cur.execute(
                f"""
                SELECT count(DISTINCT jurisdiction_code) FROM case_record {scope_filter}
                """
            )
            (jurisdiction_count,) = await cur.fetchone()  # type: ignore[misc]

            groups: list[dict[str, Any]] = []
            if group_by is not None:
                groups = await _compute_groups(cur, scope, group_by)

            await cur.execute("SELECT max(updated_at) FROM case_record")
            (last_refresh_at,) = await cur.fetchone()  # type: ignore[misc]

    result: dict[str, Any] = {
        "scope": scope,
        "totals": {
            "case_count": case_count,
            "document_count": document_count,
            "statute_count": statute_count,
            "jurisdiction_count": jurisdiction_count,
        },
        "last_refresh_at": last_refresh_at.isoformat() if last_refresh_at is not None else None,  # pyright: ignore[reportUnknownMemberType]
    }
    if group_by is not None:
        result["groups"] = groups
        result["group_by"] = group_by

    return result


async def _compute_groups(cur: Any, scope: str, group_by: str) -> list[dict[str, Any]]:
    scope_filter = ""
    if scope == "sabin":
        scope_filter = "WHERE primary_source = 'sabin'"

    if group_by == "jurisdiction":
        await cur.execute(
            f"""
            SELECT jurisdiction_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY jurisdiction_code
            ORDER BY n DESC, jurisdiction_code
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "claim_type":
        await cur.execute(
            f"""
            SELECT cct.claim_type_code, count(*) as n
            FROM case_claim_type cct
            JOIN case_record c ON c.id = cct.case_id
            {scope_filter}
            GROUP BY cct.claim_type_code
            ORDER BY n DESC, cct.claim_type_code
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "year":
        await cur.execute(
            f"""
            SELECT extract(year from filing_date)::int AS y, count(*) AS n
            FROM case_record
            {scope_filter}
            {"AND" if scope_filter else "WHERE"} filing_date IS NOT NULL
            GROUP BY y
            ORDER BY y
            """
        )
        return [{"key": str(r[0]), "count": r[1]} for r in await cur.fetchall()]
    if group_by == "status":
        await cur.execute(
            f"""
            SELECT status_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY status_code
            ORDER BY n DESC NULLS LAST
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]
    if group_by == "outcome":
        await cur.execute(
            f"""
            SELECT outcome_code, count(*) as n
            FROM case_record
            {scope_filter}
            GROUP BY outcome_code
            ORDER BY n DESC NULLS LAST
            """
        )
        return [{"key": r[0], "count": r[1]} for r in await cur.fetchall()]

    return []
