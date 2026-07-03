"""Application configuration.

Configuration is intentionally centralized and strongly typed so provider, storage,
and execution behavior can evolve without leaking environment handling into domain code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
MarketDataProvider = Literal["yahoo"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "config/local.env"),
        env_file_encoding="utf-8",
        env_prefix="KOC3_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "KOC3 Quant Platform"
    environment: Environment = "local"
    api_v1_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    demo_mode: bool = False
    market_data_provider: MarketDataProvider = "yahoo"
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://koc3:koc3@localhost:5432/koc3"
    )
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for dependency injection."""

    return Settings()
