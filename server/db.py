from psycopg_pool import AsyncConnectionPool

from server.settings import get_settings

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            # Validate each connection before lending it out — without this,
            # connections that postgres TCP-closed during idle periods (or
            # during the disk-recovery incident) hand the user a confusing
            # "server closed the connection unexpectedly" on their first
            # MCP call. The check is a cheap SELECT 1.
            check=AsyncConnectionPool.check_connection,
            # Prune connections that have been idle for >5 min so we don't
            # accumulate dead handles in the pool.
            max_idle=300,
            open=False,
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
