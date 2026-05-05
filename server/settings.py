from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"
    server_host: str = "0.0.0.0"
    server_port: int = 8000


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
