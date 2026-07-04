import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import OptionsStyle
from backend.app.application.options_forward_ledger import OptionsForwardLedgerService
from backend.app.domain.entities import Bar
from backend.app.domain.options import OptionChain, OptionContract, OptionType
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

INITIAL_CASH = Decimal("5000")


class _FakeMarketDataProvider:
    provider_name = "fake"

    def __init__(self, closes: list[Decimal]) -> None:
        self._closes = closes

    def fetch_daily_history(
        self, request: HistoricalMarketDataRequest
    ) -> HistoricalMarketData:
        # End the series at "now" so the AI signal's evaluated_at (wall-clock)
        # never precedes the most recent bar.
        start = datetime.now(UTC) - timedelta(days=len(self._closes) - 1)
        bars = tuple(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=start + timedelta(days=index),
                open=Price(close),
                high=Price(close + Decimal("1")),
                low=Price(close - Decimal("1")),
                close=Price(close),
                volume=1_000_000,
            )
            for index, close in enumerate(self._closes)
        )
        return HistoricalMarketData(
            request=request,
            bars=bars,
            corporate_actions=(),
            lineage=ProviderLineage(
                provider="fake",
                dataset="test",
                symbol=request.symbol,
                adjustment_policy="none",
                retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
            ),
        )


class _FakeOptionsProvider:
    def __init__(self, chain: OptionChain | None) -> None:
        self._chain = chain

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        if self._chain is None:
            raise RuntimeError("chain unavailable")
        return self._chain


def _bullish_closes(count: int = 260, phase: int = 48) -> list[Decimal]:
    # An oscillating series sampled at a phase whose most recent window drives
    # the AI agents to an unambiguous BUY (verified against the real agents).
    return [
        Decimal("120") + Decimal(str(round(15 * math.sin((index + phase) / 12), 4)))
        for index in range(count)
    ]


def _call_contract(strike: str = "130", dte: int = 5) -> OptionContract:
    today = datetime.now(UTC).date()
    return OptionContract(
        contract_symbol="TEST250101C00130000",
        option_type=OptionType.CALL,
        strike=Decimal(strike),
        expiration=today + timedelta(days=dte),
        days_to_expiry=dte,
        last_price=Decimal("2.50"),
        bid=Decimal("2.40"),
        ask=Decimal("2.60"),
        volume=500,
        open_interest=1000,
        implied_volatility=Decimal("0.3"),
        in_the_money=False,
    )


def _ledger(chain: OptionChain | None, closes: list[Decimal]) -> OptionsForwardLedgerService:
    market_data = MarketDataService(_FakeMarketDataProvider(closes))
    options = _FakeOptionsProvider(chain)
    return OptionsForwardLedgerService(options=options, market_data=market_data)


def test_open_if_signal_uses_real_chain_price_not_a_model() -> None:
    contract = _call_contract()
    chain = OptionChain(
        symbol="TEST",
        underlying_price=Decimal("129"),
        retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
        contracts=(contract,),
    )
    ledger = _ledger(chain, _bullish_closes())
    ledger.ensure_symbol("TEST", INITIAL_CASH)

    position = ledger.open_if_signal("TEST", OptionsStyle.WEEKLY, max_dte=8)

    assert position is not None
    assert position.contract_symbol == contract.contract_symbol
    # The entry premium must be the real quoted last price, not a computed model.
    assert position.entry_premium == Decimal("2.50")
    assert position.contracts >= 1
    assert ledger.cash_by_symbol["TEST"] < INITIAL_CASH


def test_open_if_signal_does_not_stack_a_second_position() -> None:
    contract = _call_contract()
    chain = OptionChain(
        symbol="TEST",
        underlying_price=Decimal("129"),
        retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
        contracts=(contract,),
    )
    ledger = _ledger(chain, _bullish_closes())
    ledger.ensure_symbol("TEST", INITIAL_CASH)

    first = ledger.open_if_signal("TEST", OptionsStyle.WEEKLY, max_dte=8)
    second = ledger.open_if_signal("TEST", OptionsStyle.WEEKLY, max_dte=8)

    assert first is not None
    assert second is None


def test_tick_settles_delisted_contract_using_real_underlying_intrinsic() -> None:
    contract = _call_contract(strike="130", dte=5)
    chain = OptionChain(
        symbol="TEST",
        underlying_price=Decimal("129"),
        retrieved_at_utc_iso="2026-01-01T00:00:00+00:00",
        contracts=(contract,),
    )
    ledger = _ledger(chain, _bullish_closes())
    ledger.ensure_symbol("TEST", INITIAL_CASH)
    position = ledger.open_if_signal("TEST", OptionsStyle.WEEKLY, max_dte=8)
    assert position is not None

    # The contract has now rolled off the live chain (expired) -> settle it using
    # the real underlying close, not a modeled premium.
    ledger.options = _FakeOptionsProvider(  # type: ignore[assignment]
        OptionChain(
            symbol="TEST",
            underlying_price=Decimal("135"),
            retrieved_at_utc_iso="2026-01-06T00:00:00+00:00",
            contracts=(),
        )
    )
    closed = ledger.tick()

    assert len(closed) == 1
    assert closed[0].settlement == "real_underlying_intrinsic_settlement"
    assert closed[0].id == position.id
    assert position.id not in ledger.open_positions


def test_mark_open_positions_reports_none_when_chain_unavailable() -> None:
    ledger = _ledger(None, _bullish_closes())
    ledger.ensure_symbol("TEST", INITIAL_CASH)
    # Manually seed an open position since the chain is unavailable for opening.
    from uuid import uuid4

    from backend.app.application.options_forward_ledger import OpenLedgerPosition
    from backend.app.application.options_pricing import OptionSide

    position = OpenLedgerPosition(
        id=uuid4(),
        symbol="TEST",
        style=OptionsStyle.WEEKLY,
        option_side=OptionSide.CALL,
        contract_symbol="TEST250101C00130000",
        strike=Decimal("130"),
        expiration=datetime.now(UTC).date() + timedelta(days=5),
        opened_at=datetime.now(UTC),
        entry_underlying=Decimal("129"),
        entry_premium=Decimal("2.50"),
        contracts=1,
        entry_reason="test",
    )
    ledger.open_positions[position.id] = position

    marks = ledger.mark_open_positions()

    assert len(marks) == 1
    assert marks[0].mark_premium is None
    assert marks[0].unrealized_pnl is None
