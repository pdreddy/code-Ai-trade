from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest

from backend.app.application.market_data import MarketDataService
from backend.app.domain.entities import Bar
from backend.app.domain.options import OptionChain, OptionContract, OptionType
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

pytest.importorskip("fastapi", reason="FastAPI dependency is required for API tests")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.v1.market_data import get_market_data_service  # noqa: E402
from backend.app.api.v1.options import get_options_provider  # noqa: E402
from backend.app.main import create_app  # noqa: E402

HISTORY_BAR_COUNT = 300
NEAR_TERM_MAX_DTE = 8
EXPECTED_NEAR_TERM_COUNT = 3


def _upward(index: int) -> Decimal:
    return Decimal("100") + Decimal(index) / Decimal("10")


class _StubMarketProvider:
    provider_name = "stub"

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime(2016, 1, 1, tzinfo=UTC)
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
            for index in range(HISTORY_BAR_COUNT)
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


class _StubOptionsProvider:
    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        today = datetime.now(UTC).date()
        contracts = (
            # 0DTE call with unusual activity (volume >> open interest).
            OptionContract(
                contract_symbol=f"{symbol}0DTEC",
                option_type=OptionType.CALL,
                strike=Decimal("130"),
                expiration=today,
                days_to_expiry=0,
                last_price=Decimal("1.20"),
                bid=Decimal("1.10"),
                ask=Decimal("1.30"),
                volume=5000,
                open_interest=200,
                implied_volatility=Decimal("0.55"),
                in_the_money=True,
            ),
            # Weekly call near the money.
            OptionContract(
                contract_symbol=f"{symbol}WKC",
                option_type=OptionType.CALL,
                strike=Decimal("131"),
                expiration=today + timedelta(days=5),
                days_to_expiry=5,
                last_price=Decimal("2.00"),
                bid=Decimal("1.90"),
                ask=Decimal("2.10"),
                volume=800,
                open_interest=1500,
                implied_volatility=Decimal("0.45"),
                in_the_money=False,
            ),
            # Weekly put (opposite direction).
            OptionContract(
                contract_symbol=f"{symbol}WKP",
                option_type=OptionType.PUT,
                strike=Decimal("129"),
                expiration=today + timedelta(days=5),
                days_to_expiry=5,
                last_price=Decimal("1.50"),
                bid=Decimal("1.40"),
                ask=Decimal("1.60"),
                volume=120,
                open_interest=90,
                implied_volatility=Decimal("0.48"),
                in_the_money=False,
            ),
            # Far-dated contract that must be filtered out of the near-term view.
            OptionContract(
                contract_symbol=f"{symbol}FAR",
                option_type=OptionType.CALL,
                strike=Decimal("140"),
                expiration=today + timedelta(days=30),
                days_to_expiry=30,
                last_price=Decimal("3.00"),
                bid=Decimal("2.90"),
                ask=Decimal("3.10"),
                volume=10000,
                open_interest=10,
                implied_volatility=Decimal("0.60"),
                in_the_money=False,
            ),
        )
        return OptionChain(
            symbol=symbol.upper(),
            underlying_price=Decimal("130"),
            retrieved_at_utc_iso="2026-07-04T00:00:00+00:00",
            contracts=contracts,
        )


def _market_data_service_override() -> MarketDataService:
    return MarketDataService(_StubMarketProvider())


def _options_provider_override() -> _StubOptionsProvider:
    return _StubOptionsProvider()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = _market_data_service_override
    app.dependency_overrides[get_options_provider] = _options_provider_override
    return TestClient(app)


def test_options_endpoint_returns_near_term_unusual_and_planned() -> None:
    client = _client()

    response = client.get("/api/v1/options/SPY", params={"max_dte": NEAR_TERM_MAX_DTE})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbol"] == "SPY"
    assert payload["underlying_price"] == "130"
    # The 30-day contract is excluded; three near-term contracts remain.
    assert payload["near_term_count"] == EXPECTED_NEAR_TERM_COUNT
    assert payload["zero_dte_count"] == 1
    assert payload["signal"]["action"] in {"buy", "sell", "hold"}

    # The 0DTE call traded 25x its open interest and must top unusual activity.
    assert payload["unusual_activity"], "expected unusual activity"
    assert payload["unusual_activity"][0]["contract"]["contract_symbol"] == "SPY0DTEC"
    assert Decimal(payload["unusual_activity"][0]["volume_oi_ratio"]) >= Decimal("1")

    # Only near-term contracts appear in unusual activity (the far one is filtered).
    for item in payload["unusual_activity"]:
        assert item["contract"]["days_to_expiry"] <= NEAR_TERM_MAX_DTE


def test_options_endpoint_rejects_bad_symbol_length() -> None:
    client = _client()

    response = client.get("/api/v1/options/TOOLONGSYMBOL")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_options_strategy_playbook_lists_required_first_strategies() -> None:
    client = _client()

    response = client.get("/api/v1/options/strategies")

    assert response.status_code == HTTPStatus.OK
    keys = {item["key"] for item in response.json()}
    assert keys == {
        "unusual_options_flow",
        "opening_range_breakout",
        "gamma_squeeze",
        "iv_crush",
        "earnings_momentum",
        "wheel",
        "credit_spread_scanner",
        "debit_spread_scanner",
        "zero_dte_spx",
        "spy_momentum",
    }
