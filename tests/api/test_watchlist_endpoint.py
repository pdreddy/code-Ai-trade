from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest

from backend.app.application.market_data import MarketDataService
from backend.app.domain.entities import Bar
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

pytest.importorskip("fastapi", reason="FastAPI dependency is required for API tests")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.v1.market_data import get_market_data_service  # noqa: E402
from backend.app.main import create_app  # noqa: E402

BAR_COUNT = 260
TWO_SYMBOLS = 2
DEFAULT_UNIVERSE_COUNT = 15


def _upward(index: int) -> Decimal:
    return Decimal("100") + Decimal(index) / Decimal("10")


class _StubProvider:
    provider_name = "stub"

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime.now(UTC) - timedelta(days=BAR_COUNT - 1)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(_upward(index)),
                high=Price(_upward(index) + Decimal("2")),
                low=Price(_upward(index) - Decimal("2")),
                close=Price(_upward(index)),
                volume=1_000_000 + index,
                adjusted_close=Price(_upward(index)),
            )
            for index in range(BAR_COUNT)
        )
        return HistoricalMarketData(
            request=request,
            bars=bars,
            corporate_actions=(),
            lineage=ProviderLineage(
                provider="stub",
                dataset="test",
                symbol=request.symbol,
                adjustment_policy="none",
                retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            ),
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        _StubProvider()
    )
    return TestClient(app)


def test_watchlist_returns_real_quotes_and_actions_for_two_symbols() -> None:
    client = _client()

    response = client.get("/api/v1/watchlist", params={"symbols": ["AAPL", "MSFT"]})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert len(payload["quotes"]) == TWO_SYMBOLS
    assert payload["errors"] == []
    for quote in payload["quotes"]:
        assert quote["symbol"] in {"AAPL", "MSFT"}
        assert quote["action"] in {"buy", "sell", "hold"}
        assert Decimal(quote["last_close"]) > Decimal("0")
        assert quote["change_pct"] is not None


def test_watchlist_defaults_to_full_universe() -> None:
    client = _client()

    response = client.get("/api/v1/watchlist")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert len(payload["quotes"]) == DEFAULT_UNIVERSE_COUNT
