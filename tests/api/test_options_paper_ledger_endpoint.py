import math
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

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.v1.market_data import get_market_data_service  # noqa: E402
from backend.app.api.v1.options import get_options_provider  # noqa: E402
from backend.app.main import create_app  # noqa: E402

BAR_COUNT = 260
BULLISH_PHASE = 48


def _oscillating(index: int, phase: int = BULLISH_PHASE) -> Decimal:
    return Decimal("120") + Decimal(str(round(15 * math.sin((index + phase) / 12), 4)))


class _StubMarketProvider:
    provider_name = "stub"

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime.now(UTC) - timedelta(days=BAR_COUNT - 1)
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
                retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            ),
        )


class _StubOptionsProvider:
    """Always offers one real, live-quoted near-term call."""

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        today = datetime.now(UTC).date()
        contract = OptionContract(
            contract_symbol=f"{symbol}TESTCALL",
            option_type=OptionType.CALL,
            strike=Decimal("130"),
            expiration=today + timedelta(days=5),
            days_to_expiry=5,
            last_price=Decimal("2.50"),
            bid=Decimal("2.40"),
            ask=Decimal("2.60"),
            volume=500,
            open_interest=1000,
            implied_volatility=Decimal("0.3"),
            in_the_money=False,
        )
        return OptionChain(
            symbol=symbol.upper(),
            underlying_price=Decimal("129"),
            retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            contracts=(contract,),
        )


class _EmptyOptionsProvider:
    """Simulates every previously-offered contract rolling off the chain."""

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        return OptionChain(
            symbol=symbol.upper(),
            underlying_price=Decimal("135"),
            retrieved_at_utc_iso="2026-01-06T00:00:00+00:00",
            contracts=(),
        )


def _market_data_service_override() -> MarketDataService:
    return MarketDataService(_StubMarketProvider())


def _options_provider_override() -> _StubOptionsProvider:
    return _StubOptionsProvider()


def _client() -> tuple[FastAPI, TestClient]:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = _market_data_service_override
    app.dependency_overrides[get_options_provider] = _options_provider_override
    return app, TestClient(app)


def test_paper_ledger_tick_opens_positions_from_real_chain_prices() -> None:
    app, client = _client()

    response = client.post("/api/v1/options-portfolio/paper-ledger/tick")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["real_quotes"] is True
    assert len(payload["open_positions"]) > 0
    for position in payload["open_positions"]:
        # The entry premium must be the stub's real quoted last price (2.50),
        # never a Black-Scholes model output.
        assert position["entry_premium"] == "2.50"
    del app


def test_paper_ledger_get_is_read_only() -> None:
    app, client = _client()

    before = client.get("/api/v1/options-portfolio/paper-ledger").json()
    after = client.get("/api/v1/options-portfolio/paper-ledger").json()

    assert before["open_positions"] == []
    assert after["open_positions"] == []
    del app


def test_paper_ledger_tick_settles_positions_that_roll_off_the_chain() -> None:
    app, client = _client()

    opened = client.post("/api/v1/options-portfolio/paper-ledger/tick").json()
    assert len(opened["open_positions"]) > 0

    # Simulate every open contract rolling off the live chain (expiry/delisting)
    # by swapping the ledger's options provider in place, exactly as a real
    # options chain would stop listing an expired contract.
    app.state.options_ledger.options = _EmptyOptionsProvider()

    settled = client.post("/api/v1/options-portfolio/paper-ledger/tick").json()

    assert len(settled["closed_positions"]) == len(opened["open_positions"])
    for position in settled["closed_positions"]:
        assert position["settlement"] == "real_underlying_intrinsic_settlement"
    assert settled["open_positions"] == []
