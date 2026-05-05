import os

import pytest


@pytest.fixture(autouse=True)
def _set_database_url(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL", "postgresql://openclimate:dev@localhost:5432/openclimate"),
    )
