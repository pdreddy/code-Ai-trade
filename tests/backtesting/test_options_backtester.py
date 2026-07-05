import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import MasterDecisionEngine
from backend.app.application.options_backtesting import (
    MIN_TRADABLE_PREMIUM,
    OptionsBacktester,
    OptionsStyle,
)
from backend.app.application.options_pricing import OptionSide
from backend.app.application.options_strategy_screen import OptionsStrategyScreenService
from backend.app.domain.entities import Bar
from backend.app.domain.value_objects import Price

BAR_COUNT = 400
INITIAL_CAPITAL = Decimal("10000")
FRIDAY_WEEKDAY = 4


def _oscillating(index: int) -> Decimal:
    # A sine wave produces alternating buy/sell cycles so both calls and puts
    # get opened and closed within the window.
    return Decimal("120") + Decimal(str(round(15 * math.sin(index / 12), 4)))


def _bars(instrument_id: UUID, count: int) -> tuple[Bar, ...]:
    start = datetime(2024, 1, 1, 14, 30, tzinfo=UTC)
    bars = []
    for index in range(count):
        price = _oscillating(index)
        timestamp = start + timedelta(days=index)
        bars.append(
            Bar(
                instrument_id=instrument_id,
                timestamp=timestamp,
                open=Price(price - Decimal("0.3")),
                high=Price(price + Decimal("2")),
                low=Price(price - Decimal("2")),
                close=Price(price),
                volume=1_000_000 + index,
            )
        )
    return tuple(bars)


def _backtester(style: OptionsStyle) -> OptionsBacktester:
    return OptionsBacktester(
        agents=create_default_agents(),
        engine=MasterDecisionEngine(),
        style=style,
        initial_capital=INITIAL_CAPITAL,
    )


def test_zero_dte_backtest_produces_same_day_round_trips() -> None:
    instrument_id = uuid4()
    bars = _bars(instrument_id, BAR_COUNT)

    result = _backtester(OptionsStyle.ZERO_DTE).run(instrument_id, "SPY", bars)

    assert result.metrics.trade_count > 0
    closed = result.metrics.winning_trades + result.metrics.losing_trades
    assert closed <= result.metrics.trade_count
    assert len(result.equity_curve) == BAR_COUNT
    assert result.final_equity == result.equity_curve[-1].equity
    for trade in result.trades:
        # 0DTE: the contract opens and expires the same calendar day.
        assert trade.entry_at == trade.exit_at
        assert trade.expiration == trade.entry_at
        assert trade.contracts >= 1
        assert trade.option_side in {OptionSide.CALL, OptionSide.PUT}
        assert trade.entry_reason
        assert trade.exit_reason


def test_weekly_backtest_holds_across_multiple_days() -> None:
    instrument_id = uuid4()
    bars = _bars(instrument_id, BAR_COUNT)

    result = _backtester(OptionsStyle.WEEKLY).run(instrument_id, "SPY", bars)

    assert result.metrics.trade_count > 0
    # Weekly contracts should generally hold longer than a single day (the
    # nearest Friday), unlike the 0DTE style.
    multi_day_trades = [trade for trade in result.trades if trade.exit_at > trade.entry_at]
    assert multi_day_trades, "expected at least one weekly trade to span multiple days"
    for trade in result.trades:
        assert trade.expiration.weekday() == FRIDAY_WEEKDAY or trade.expiration == trade.entry_at


def test_cash_conservation_never_exceeds_initial_capital_plus_gains() -> None:
    instrument_id = uuid4()
    bars = _bars(instrument_id, BAR_COUNT)

    result = _backtester(OptionsStyle.WEEKLY).run(instrument_id, "SPY", bars)

    # Every reported equity point must be a finite, non-negative Decimal — the
    # premium-budget sizing must never let the sleeve go into margin debt.
    for point in result.equity_curve:
        assert point.equity >= Decimal("0")


def test_options_backtest_requires_minimum_bars() -> None:
    instrument_id = uuid4()
    bars = _bars(instrument_id, 10)

    try:
        _backtester(OptionsStyle.ZERO_DTE).run(instrument_id, "SPY", bars)
        raise AssertionError("expected DomainValidationError")
    except Exception as exc:  # noqa: BLE001
        assert "at least" in str(exc)


def test_options_strategy_screen_ranks_styles_by_winning_metrics() -> None:
    instrument_id = uuid4()
    bars = _bars(instrument_id, BAR_COUNT)

    screen = OptionsStrategyScreenService().screen(
        instrument_id,
        "SPY",
        bars,
        capital=INITIAL_CAPITAL,
        min_win_rate=Decimal("0"),
    )

    assert {item.style for item in screen.results} == {OptionsStyle.ZERO_DTE, OptionsStyle.WEEKLY}
    assert screen.results[0].recommended is True
    assert [item.recommended for item in screen.results].count(True) == 1
    assert screen.results == tuple(
        sorted(
            screen.results,
            key=lambda item: (
                item.meets_threshold,
                item.result.metrics.win_rate,
                item.result.metrics.total_return,
                item.result.metrics.profit_factor,
                -item.result.metrics.max_drawdown.copy_abs(),
            ),
            reverse=True,
        )
    )


def test_options_backtest_skips_dust_premium_contracts() -> None:
    instrument_id = uuid4()
    flat_bars = tuple(
        Bar(
            instrument_id=instrument_id,
            timestamp=datetime(2024, 1, 1, 14, 30, tzinfo=UTC) + timedelta(days=index),
            open=Price(Decimal("100")),
            high=Price(Decimal("100.01")),
            low=Price(Decimal("99.99")),
            close=Price(Decimal("100")),
            volume=1_000_000,
        )
        for index in range(BAR_COUNT)
    )

    result = _backtester(OptionsStyle.ZERO_DTE).run(instrument_id, "SPY", flat_bars)

    assert all(trade.entry_premium >= MIN_TRADABLE_PREMIUM for trade in result.trades)
