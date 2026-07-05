"""Application services for market-data retrieval."""

from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    MarketDataProvider,
)


class MarketDataService:
    """Use-case service that isolates callers from provider-specific adapters."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData:
        """Fetch normalized daily history from the configured market-data provider."""

        return self._provider.fetch_daily_history(request)
