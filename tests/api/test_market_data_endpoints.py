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


class _StubProvider:
    """In-memory provider that returns a deterministic upward series (no network)."""

    provider_name = "stub"

    def __init__(self, bar_count: int) -> None:
        self._bar_count = bar_count

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(Decimal("100") + Decimal(index) / Decimal("10")),
                high=Price(Decimal("101") + Decimal(index) / Decimal("10")),
                low=Price(Decimal("99") + Decimal(index) / Decimal("10")),
                close=Price(Decimal("100") + Decimal(index) / Decimal("10")),
                volume=1_000_000 + index,
                adjusted_close=Price(Decimal("100") + Decimal(index) / Decimal("10")),
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
                retrieved_at_utc_iso="2024-01-01T00:00:00+00:00",
            ),
        )


def _client(bar_count: int) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        _StubProvider(bar_count)
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
