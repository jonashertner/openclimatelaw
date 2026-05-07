import os
from collections.abc import AsyncGenerator

import pytest


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql://openclimate:dev@localhost:5432/openclimate"),
    )


@pytest.fixture(autouse=True)
async def _teardown_pool() -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction]
    """Close the connection pool after each test so the next test gets a fresh pool."""
    yield
    from server.db import close_pool

    await close_pool()
