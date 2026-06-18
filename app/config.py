from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5432/booking"
    redis_url: str = "redis://localhost:6379/0"

    # Worker settings
    failure_rate: float = 0.15
    max_retries: int = 3
    retry_base_delay: float = 2.0
    retry_max_delay: float = 60.0

    # Rate limiting
    rate_limit: str = "10/minute"
    rate_limit_storage: str = "memory://"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
