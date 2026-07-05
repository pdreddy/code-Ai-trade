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
OptionsDataProvider = Literal["yahoo", "tradier"]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "config/local.env"),
        env_file_encoding="utf-8",
        env_prefix="AI_QUANT_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Quant Platform"
    environment: Environment = "local"
    api_v1_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    demo_mode: bool = False
    market_data_provider: MarketDataProvider = "yahoo"
    # Yahoo's undocumented options endpoint blocks server/datacenter IPs far more
    # aggressively than its chart endpoint, so a real alternative (Tradier's free
    # developer sandbox) is available behind the same OptionsProvider contract.
    options_data_provider: OptionsDataProvider = "yahoo"
    tradier_api_token: str | None = None
    tradier_base_url: str = "https://sandbox.tradier.com/v1"
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://quant:quant@localhost:5432/quant")
    )
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for dependency injection."""

    return Settings()
