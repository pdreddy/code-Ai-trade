import math
from collections.abc import Callable
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

AGENT_COUNT = 10
HISTORY_BAR_COUNT = 60
SIGNAL_BAR_COUNT = 260
BACKTEST_BAR_COUNT = 400


def _upward(index: int) -> Decimal:
    return Decimal("100") + Decimal(index) / Decimal("10")


def _oscillating(index: int) -> Decimal:
    # A sine wave produces alternating buy/sell cycles so trades actually close.
    return Decimal("120") + Decimal(str(round(15 * math.sin(index / 12), 4)))


class _StubProvider:
    """In-memory provider returning a deterministic price series (no network)."""

    provider_name = "stub"

    def __init__(self, bar_count: int, price: Callable[[int], Decimal] = _upward) -> None:
        self._bar_count = bar_count
        self._price = price

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime(2016, 1, 1, tzinfo=UTC)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(self._price(index)),
                high=Price(self._price(index) + Decimal("2")),
                low=Price(self._price(index) - Decimal("2")),
                close=Price(self._price(index)),
                volume=1_000_000 + index,
                adjusted_close=Price(self._price(index)),
            )
            for index in range(self._bar_count)
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


def _client(bar_count: int, price: Callable[[int], Decimal] = _upward) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        _StubProvider(bar_count, price)
    )
    return TestClient(app)


def test_history_endpoint_returns_real_bars() -> None:
    client = _client(bar_count=HISTORY_BAR_COUNT)

    response = client.get("/api/v1/market-data/SPY/history", params={"days": 90})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["provider"] == "stub"
    assert payload["bar_count"] == HISTORY_BAR_COUNT
    assert len(payload["bars"]) == HISTORY_BAR_COUNT
    assert payload["bars"][0]["close"] == "100"


def test_signals_endpoint_runs_all_agents_and_master_decision() -> None:
    client = _client(bar_count=SIGNAL_BAR_COUNT)

    response = client.get("/api/v1/market-data/SPY/signals", params={"days": 420})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["bar_count"] == SIGNAL_BAR_COUNT
    assert len(payload["votes"]) == AGENT_COUNT
    assert payload["master_decision"]["action"] in {"buy", "sell", "hold"}
    assert {vote["agent_name"] for vote in payload["votes"]} == {
        "trend",
        "momentum",
        "volatility",
        "risk",
        "portfolio",
        "mean_reversion",
        "breakout",
        "support_resistance",
        "volume",
        "market_regime",
    }


def test_history_endpoint_rejects_non_alphanumeric_symbol() -> None:
    client = _client(bar_count=HISTORY_BAR_COUNT)

    response = client.get("/api/v1/market-data/BRK.B/history")

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_backtest_endpoint_executes_trades_with_success_rate_and_next_signal() -> None:
    client = _client(bar_count=BACKTEST_BAR_COUNT, price=_oscillating)

    response = client.get("/api/v1/market-data/SPY/backtest", params={"days": 1200})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["bar_count"] == BACKTEST_BAR_COUNT
    metrics = payload["metrics"]
    # The oscillating series must generate closed round-trip trades.
    assert metrics["trade_count"] > 0
    assert metrics["winning_trades"] + metrics["losing_trades"] <= metrics["trade_count"]
    assert Decimal(metrics["success_rate"]) >= Decimal("0")
    assert len(payload["trades"]) == metrics["trade_count"]
    assert len(payload["equity_curve"]) == BACKTEST_BAR_COUNT
    assert payload["next_signal"]["action"] in {"buy", "sell", "hold"}
    for trade in payload["trades"]:
        assert trade["entry_price"] is not None
        assert trade["realized_pnl"] is not None


def test_history_endpoint_supports_ten_year_range() -> None:
    client = _client(bar_count=HISTORY_BAR_COUNT)

    within_range = client.get("/api/v1/market-data/SPY/history", params={"days": 3660})
    beyond_range = client.get("/api/v1/market-data/SPY/history", params={"days": 3661})

    assert within_range.status_code == HTTPStatus.OK
    assert beyond_range.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
