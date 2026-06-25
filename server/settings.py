from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    database_url: str
    log_level: str = "INFO"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    # Eagerly load the embedding model at startup so the first semantic search
    # after a (re)start doesn't pay the ~30-60s cold-load (and time out clients).
    prewarm_embedder: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
