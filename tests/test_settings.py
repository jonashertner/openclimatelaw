from typing import Any

from server.settings import Settings


def test_settings_reads_database_url_from_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.database_url == "postgresql://u:p@localhost:5432/db"
    assert settings.log_level == "INFO"


def test_settings_defaults_when_optional_unset(monkeypatch: Any) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    settings = Settings()  # type: ignore[call-arg]
    assert settings.log_level == "INFO"


def test_settings_requires_database_url(monkeypatch: Any) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]
