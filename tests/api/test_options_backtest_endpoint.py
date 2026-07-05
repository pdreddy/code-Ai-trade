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
DEFAULT_OPTIONS_UNIVERSE_COUNT = 10


def _oscillating(index: int) -> Decimal:
    return Decimal("120") + Decimal(str(round(15 * math.sin(index / 12), 4)))


class _StubProvider:
    provider_name = "stub"

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(_oscillating(index) - Decimal("0.3")),
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
                retrieved_at_utc_iso="2024-01-01T00:00:00+00:00",
            ),
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(_StubProvider())
    return TestClient(app)


def test_options_backtest_endpoint_is_labeled_modeled() -> None:
    client = _client()

    response = client.get(
        "/api/v1/options/SPY/backtest",
        params={"style": "zero_dte", "days": 1200, "capital": "10000"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["style"] == "zero_dte"
    assert payload["modeled"] is True
    assert "Black-Scholes" in payload["pricing_note"]
    assert payload["metrics"]["trade_count"] > 0
    assert len(payload["trades"]) == payload["metrics"]["trade_count"]
    for trade in payload["trades"]:
        assert trade["option_side"] in {"call", "put"}
        assert trade["entry_at"] == trade["exit_at"]  # 0DTE same-day round trip


def test_options_backtest_endpoint_supports_weekly_style() -> None:
    client = _client()

    response = client.get("/api/v1/options/SPY/backtest", params={"style": "weekly", "days": 1200})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["style"] == "weekly"
    assert payload["metrics"]["trade_count"] > 0


def test_options_strategy_screen_endpoint_recommends_best_style() -> None:
    client = _client()

    response = client.get(
        "/api/v1/options/SPY/strategy-screen",
        params={"days": 1200, "capital": "10000", "min_win_rate": "0"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["modeled"] is True
    assert payload["recommended_style"] in {"zero_dte", "weekly"}
    assert {result["style"] for result in payload["results"]} == {"zero_dte", "weekly"}
    assert sum(1 for result in payload["results"] if result["recommended"]) == 1
    assert payload["results"][0]["recommended"] is True
    win_rates = [Decimal(result["win_rate"]) for result in payload["results"]]
    assert win_rates == sorted(win_rates, reverse=True)


def test_options_portfolio_execute_allocates_capital_across_universe() -> None:
    client = _client()

    response = client.get(
        "/api/v1/options-portfolio/execute",
        params={"symbols": ["SPY", "QQQ"], "capital": "10000", "days": 1200, "style": "weekly"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["modeled"] is True
    assert payload["symbol_count"] == TWO_SYMBOLS
    assert {sleeve["allocated"] for sleeve in payload["sleeves"]} == {"5000.00"}
    assert payload["trade_count"] > 0
    assert len(payload["trades"]) > 0
    assert payload["errors"] == []


def test_options_portfolio_execute_defaults_to_curated_universe() -> None:
    client = _client()

    response = client.get("/api/v1/options-portfolio/execute", params={"days": 600})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol_count"] == DEFAULT_OPTIONS_UNIVERSE_COUNT
