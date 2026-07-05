from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest

from backend.app.application.market_data import MarketDataService
from backend.app.domain.entities import Bar
from backend.app.domain.options import OptionChain, OptionContract, OptionsProvider, OptionType
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    MarketDataProvider,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

pytest.importorskip("fastapi", reason="FastAPI dependency is required for API tests")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.v1.market_data import get_market_data_service  # noqa: E402
from backend.app.api.v1.options import get_options_provider  # noqa: E402
from backend.app.main import create_app  # noqa: E402

BAR_COUNT = 300
TWO_SYMBOLS = 2
DEFAULT_UNIVERSE_COUNT = 18


def _upward(index: int) -> Decimal:
    return Decimal("100") + Decimal(index) / Decimal("10")


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


class _StubOptionsProvider:
    """Every symbol gets one unusual 0DTE call, with a volume proportional to
    the symbol name length so ranking is deterministic and verifiable."""

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        today = datetime.now(UTC).date()
        volume = 1000 * (len(symbol) + 1)
        contract = OptionContract(
            contract_symbol=f"{symbol}0DTEC",
            option_type=OptionType.CALL,
            strike=Decimal("130"),
            expiration=today,
            days_to_expiry=0,
            last_price=Decimal("1.20"),
            bid=Decimal("1.10"),
            ask=Decimal("1.30"),
            volume=volume,
            open_interest=100,
            implied_volatility=Decimal("0.5"),
            in_the_money=False,
        )
        return OptionChain(
            symbol=symbol.upper(),
            underlying_price=Decimal("129"),
            retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            contracts=(contract,),
        )


class _FlatThenBreakoutMarketProvider:
    """Flat prices, then a final-bar close that breaks above the 20-session high —
    the exact footprint the breakout agent looks for."""

    provider_name = "stub"

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        start = datetime.now(UTC) - timedelta(days=BAR_COUNT - 1)
        flat_price = Decimal("100")
        bars = []
        for index in range(BAR_COUNT):
            close = Decimal("112") if index == BAR_COUNT - 1 else flat_price
            bars.append(
                Bar(
                    instrument_id=request.instrument_id,
                    timestamp=start + timedelta(days=index),
                    open=Price(close),
                    high=Price(close + Decimal("2")),
                    low=Price(close - Decimal("2")),
                    close=Price(close),
                    volume=1_000_000,
                    adjusted_close=Price(close),
                )
            )
        return HistoricalMarketData(
            request=request,
            bars=tuple(bars),
            corporate_actions=(),
            lineage=ProviderLineage(
                provider="stub",
                dataset="test",
                symbol=request.symbol,
                adjustment_policy="none",
                retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            ),
        )


class _SkewedOptionsProvider:
    """Every symbol gets one heavily call-skewed OI pair (calls 10x puts)."""

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        today = datetime.now(UTC).date()
        call = OptionContract(
            contract_symbol=f"{symbol}CALL",
            option_type=OptionType.CALL,
            strike=Decimal("130"),
            expiration=today,
            days_to_expiry=0,
            last_price=Decimal("1.20"),
            bid=Decimal("1.10"),
            ask=Decimal("1.30"),
            volume=10,
            open_interest=1000,
            implied_volatility=Decimal("0.5"),
            in_the_money=False,
        )
        put = OptionContract(
            contract_symbol=f"{symbol}PUT",
            option_type=OptionType.PUT,
            strike=Decimal("130"),
            expiration=today,
            days_to_expiry=0,
            last_price=Decimal("1.00"),
            bid=Decimal("0.90"),
            ask=Decimal("1.10"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal("0.5"),
            in_the_money=False,
        )
        return OptionChain(
            symbol=symbol.upper(),
            underlying_price=Decimal("129"),
            retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            contracts=(call, put),
        )


def _client(
    market_provider: MarketDataProvider | None = None,
    options_provider: OptionsProvider | None = None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_market_data_service] = lambda: MarketDataService(
        market_provider or _StubMarketProvider()
    )
    app.dependency_overrides[get_options_provider] = lambda: (
        options_provider or _StubOptionsProvider()
    )
    return TestClient(app)


def test_scanner_merges_unusual_activity_across_symbols_ranked_together() -> None:
    client = _client()

    response = client.get(
        "/api/v1/scanner", params={"symbols": ["A", "AAAA"], "max_dte": 8}
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbols_scanned"] == TWO_SYMBOLS
    assert payload["errors"] == []
    assert len(payload["unusual_activity"]) == TWO_SYMBOLS
    # "AAAA" (longer symbol -> higher stub volume) must rank above "A".
    assert payload["unusual_activity"][0]["symbol"] == "AAAA"
    assert payload["unusual_activity"][1]["symbol"] == "A"


def test_scanner_defaults_to_full_options_universe() -> None:
    client = _client()

    response = client.get("/api/v1/scanner")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["symbols_scanned"] == DEFAULT_UNIVERSE_COUNT


def test_scanner_surfaces_oi_skew_and_breakout_sections_with_confidence() -> None:
    client = _client(
        market_provider=_FlatThenBreakoutMarketProvider(),
        options_provider=_SkewedOptionsProvider(),
    )

    response = client.get("/api/v1/scanner", params={"symbols": ["AAAA"], "max_dte": 8})

    assert response.status_code == HTTPStatus.OK
    payload = response.json()

    assert len(payload["oi_skew"]) == 1
    skew = payload["oi_skew"][0]
    assert skew["symbol"] == "AAAA"
    assert skew["direction"] == "calls"
    assert Decimal(skew["confidence"]) > Decimal("0")

    assert len(payload["breakouts"]) == 1
    breakout = payload["breakouts"][0]
    assert breakout["symbol"] == "AAAA"
    assert breakout["direction"] == "bullish"
    assert Decimal(breakout["confidence"]) > Decimal("0")

    for item in payload["unusual_activity"]:
        assert Decimal(item["confidence"]) >= Decimal("0")
