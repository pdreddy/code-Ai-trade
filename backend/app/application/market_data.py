"""Application services for market-data retrieval."""

from datetime import UTC, datetime, timedelta
from threading import RLock

from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    MarketDataProvider,
)


class MarketDataService:
    """Use-case service that isolates callers from provider-specific adapters."""

    def __init__(self, provider: MarketDataProvider, cache_ttl_seconds: int = 0) -> None:
        self._provider = provider
        self._cache_ttl = timedelta(seconds=max(cache_ttl_seconds, 0))
        self._cache: dict[HistoricalMarketDataRequest, tuple[datetime, HistoricalMarketData]] = {}
        self._cache_lock = RLock()

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData:
        """Fetch normalized daily history from the configured market-data provider."""

        if self._cache_ttl.total_seconds() <= 0:
            return self._provider.fetch_daily_history(request)

        now = datetime.now(UTC)
        with self._cache_lock:
            cached = self._cache.get(request)
            if cached is not None:
                cached_at, data = cached
                if now - cached_at <= self._cache_ttl:
                    return data
                del self._cache[request]

        data = self._provider.fetch_daily_history(request)
        with self._cache_lock:
            self._cache[request] = (now, data)
        return data
