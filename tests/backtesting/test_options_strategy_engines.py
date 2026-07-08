from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from backend.app.application.options_strategy_engines import (
    StrategyEngineContext,
    run_strategy_engines,
)
from backend.app.domain.entities import Bar
from backend.app.domain.enums import SignalAction
from backend.app.domain.options import OptionContract, OptionType
from backend.app.domain.value_objects import Price


def _bars() -> tuple[Bar, ...]:
    instrument_id = uuid4()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        Bar(
            instrument_id=instrument_id,
            timestamp=start + timedelta(days=index),
            open=Price(Decimal("100") + Decimal(index) / Decimal("10")),
            high=Price(Decimal("101") + Decimal(index) / Decimal("10")),
            low=Price(Decimal("99") + Decimal(index) / Decimal("10")),
            close=Price(Decimal("100") + Decimal(index) / Decimal("10")),
            volume=1_000_000 + index,
        )
        for index in range(70)
    )


def _contract(
    symbol: str, option_type: OptionType, strike: str, volume: int, oi: int
) -> OptionContract:
    return OptionContract(
        contract_symbol=symbol,
        option_type=option_type,
        strike=Decimal(strike),
        expiration=datetime(2026, 1, 30, tzinfo=UTC).date(),
        days_to_expiry=5,
        last_price=Decimal("0.50"),
        bid=Decimal("0.45"),
        ask=Decimal("0.55"),
        volume=volume,
        open_interest=oi,
        implied_volatility=Decimal("0.30"),
        in_the_money=False,
    )


def test_strategy_engines_emit_deterministic_pre_ai_signals() -> None:
    context = StrategyEngineContext(
        symbol="SPY",
        underlying_price=Decimal("107"),
        contracts=(
            _contract("SPY_CALL_107", OptionType.CALL, "107", 1000, 100),
            _contract("SPY_CALL_110", OptionType.CALL, "110", 800, 600),
            _contract("SPY_PUT_105", OptionType.PUT, "105", 100, 700),
        ),
        bars=_bars(),
    )

    signals = run_strategy_engines(context)

    assert {signal.engine for signal in signals} == {
        "spy_qqq_momentum",
        "unusual_options_flow",
        "gamma_exposure",
        "vwap_trend",
        "relative_strength",
        "credit_debit_spread_scanner",
    }
    assert any(signal.action is SignalAction.BUY and signal.tradable for signal in signals)
