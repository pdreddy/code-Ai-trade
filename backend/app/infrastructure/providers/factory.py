"""Provider factory for configuration-driven market-data adapter selection."""

from typing import Protocol

from backend.app.domain.providers import MarketDataProvider
from backend.app.infrastructure.providers.yahoo import YahooFinanceProvider


class MarketDataProviderSettings(Protocol):
    """Settings subset required to choose a market-data provider."""

    @property
    def market_data_provider(self) -> str: ...


def create_market_data_provider(settings: MarketDataProviderSettings) -> MarketDataProvider:
    """Create the configured market-data provider adapter."""

    if settings.market_data_provider == "yahoo":
        return YahooFinanceProvider()
    raise ValueError(f"Unsupported market data provider: {settings.market_data_provider}")
