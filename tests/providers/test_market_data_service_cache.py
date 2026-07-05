from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from backend.app.application.market_data import MarketDataService
from backend.app.domain.entities import Bar
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

EXPECTED_DISABLED_CACHE_CALLS = 2


class _CountingProvider:
    provider_name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData:
        self.calls += 1
        bar = Bar(
            instrument_id=request.instrument_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            open=Price(Decimal("100")),
            high=Price(Decimal("101")),
            low=Price(Decimal("99")),
            close=Price(Decimal("100")),
            volume=1_000,
            adjusted_close=Price(Decimal("100")),
        )
        return HistoricalMarketData(
            request=request,
            bars=(bar,),
            corporate_actions=(),
            lineage=ProviderLineage(
                provider=self.provider_name,
                dataset="unit-test",
                symbol=request.symbol,
                adjustment_policy="none",
                retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            ),
        )


def _request(symbol: str = "SPY") -> HistoricalMarketDataRequest:
    return HistoricalMarketDataRequest(
        instrument_id=uuid4(),
        symbol=symbol,
        start=date(2025, 1, 1),
        end=date(2026, 1, 1),
    )


def test_market_data_service_reuses_cached_history_within_ttl() -> None:
    provider = _CountingProvider()
    service = MarketDataService(provider, cache_ttl_seconds=60)
    request = _request()

    first = service.fetch_daily_history(request)
    second = service.fetch_daily_history(request)

    assert first is second
    assert provider.calls == 1


def test_market_data_service_cache_can_be_disabled() -> None:
    provider = _CountingProvider()
    service = MarketDataService(provider, cache_ttl_seconds=0)
    request = _request()

    first = service.fetch_daily_history(request)
    second = service.fetch_daily_history(request)

    assert first is not second
    assert provider.calls == EXPECTED_DISABLED_CACHE_CALLS
