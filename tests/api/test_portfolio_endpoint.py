import math
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

BAR_COUNT = 400
TWO_SYMBOLS = 2
DEFAULT_STOCK_UNIVERSE_COUNT = 15


def _oscillating(index: int) -> Decimal:
    return Decimal("120") + Decimal(str(round(15 * math.sin(index / 12), 4)))


class _StubProvider:
    provider_name = "stub"

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime(2016, 1, 1, tzinfo=UTC)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(_oscillating(index)),
                high=Price(_oscillating(index) + Decimal("2")),
                low=Price(_oscillating(index) - Decimal("2")),
                close=Price(_oscillating(index)),
                volume=1_000_000 + index,
                adjusted_close=Price(_oscillating(index)),
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
                retrieved_at_utc_iso="2016-01-01T00:00:00+00:00",
            ),
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        _StubProvider()
    )
    return TestClient(app)


def test_execute_portfolio_allocates_capital_and_aggregates_trades() -> None:
    client = _client()

    response = client.get(
        "/api/v1/portfolio/execute",
        params={"symbols": ["SPY", "QQQ"], "capital": "10000", "days": 1200},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["initial_capital"] == "10000"
    assert payload["symbol_count"] == TWO_SYMBOLS
    assert len(payload["sleeves"]) == TWO_SYMBOLS
    # Each sleeve receives an equal slice of the shared capital base.
    assert {sleeve["allocated"] for sleeve in payload["sleeves"]} == {"5000.00"}
    assert payload["trade_count"] > 0
    assert len(payload["trades"]) > 0
    assert payload["winning_trades"] + payload["losing_trades"] <= payload["trade_count"]
    assert Decimal(payload["success_rate"]) >= Decimal("0")
    assert len(payload["equity_curve"]) == BAR_COUNT
    # Cash + invested reconciles to total equity.
    assert Decimal(payload["cash"]) + Decimal(payload["invested"]) == Decimal(
        payload["total_equity"]
    )
    for sleeve in payload["sleeves"]:
        assert sleeve["next_signal"]["action"] in {"buy", "sell", "hold"}


def test_execute_portfolio_defaults_to_full_universe() -> None:
    client = _client()

    response = client.get("/api/v1/portfolio/execute", params={"days": 600})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol_count"] == DEFAULT_STOCK_UNIVERSE_COUNT
    assert payload["errors"] == []
