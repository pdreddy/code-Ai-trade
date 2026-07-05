from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.domain import (
    AssetClass,
    BacktestRun,
    Bar,
    Confidence,
    DomainValidationError,
    Instrument,
    Order,
    OrderSide,
    OrderState,
    OrderType,
    Portfolio,
    PortfolioPosition,
    Price,
    Quantity,
    RiskFraction,
    SignalAction,
    TimeInForce,
)
from backend.app.domain.entities import AgentSignal, MasterDecision, Trade


def test_bar_rejects_inconsistent_ohlc_values() -> None:
    instrument_id = uuid4()

    with pytest.raises(DomainValidationError, match="bar high"):
        Bar(
            instrument_id=instrument_id,
            timestamp=datetime(2025, 1, 2, 21, tzinfo=UTC),
            open=Price(Decimal("100")),
            high=Price(Decimal("99")),
            low=Price(Decimal("98")),
            close=Price(Decimal("100")),
            volume=1_000_000,
        )


def test_signal_and_master_decision_require_auditable_reasons() -> None:
    instrument_id = uuid4()
    generated_at = datetime(2025, 1, 2, 21, 1, tzinfo=UTC)
    signal_bar_timestamp = datetime(2025, 1, 2, 21, tzinfo=UTC)

    signal = AgentSignal(
        id=uuid4(),
        instrument_id=instrument_id,
        agent_name="trend",
        action=SignalAction.BUY,
        confidence=Confidence(Decimal("0.82")),
        score=Decimal("1.7"),
        reasons=("close above rising 200-day moving average",),
        generated_at=generated_at,
        signal_bar_timestamp=signal_bar_timestamp,
    )

    decision = MasterDecision(
        id=uuid4(),
        instrument_id=instrument_id,
        action=SignalAction.BUY,
        confidence=Confidence(Decimal("0.76")),
        risk_score=RiskFraction(Decimal("0.24")),
        stop_loss=Price(Decimal("470")),
        take_profit=Price(Decimal("510")),
        expected_r_multiple=Decimal("2.1"),
        explanation="Trend and momentum agents agree while risk remains inside mandate.",
        agent_signal_ids=(signal.id,),
        generated_at=generated_at + timedelta(seconds=2),
        signal_bar_timestamp=signal_bar_timestamp,
    )

    assert decision.agent_signal_ids == (signal.id,)


def test_order_state_invariants_prevent_partial_execution_records() -> None:
    with pytest.raises(DomainValidationError, match="filled orders"):
        Order(
            id=uuid4(),
            instrument_id=uuid4(),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            state=OrderState.FILLED,
            quantity=Quantity(Decimal("10")),
            submitted_at=datetime(2025, 1, 3, 14, 30, tzinfo=UTC),
            time_in_force=TimeInForce.DAY,
        )


def test_portfolio_equity_and_position_pnl_are_decimal_exact() -> None:
    position = PortfolioPosition(
        instrument_id=uuid4(),
        quantity=Quantity(Decimal("12.5")),
        average_cost=Price(Decimal("100.10")),
        market_price=Price(Decimal("102.30")),
        as_of=datetime(2025, 1, 3, 21, tzinfo=UTC),
    )
    portfolio = Portfolio(
        id=uuid4(),
        name="Research Portfolio",
        base_currency="USD",
        cash=Decimal("10000.00"),
        positions=(position,),
        as_of=position.as_of,
    )

    assert position.unrealized_pnl == Decimal("27.500")
    assert portfolio.equity == Decimal("11278.750")


def test_backtest_run_enforces_temporal_and_cost_invariants() -> None:
    instrument = Instrument(
        id=uuid4(),
        symbol="SPY",
        name="SPDR S&P 500 ETF Trust",
        exchange="ARCX",
        asset_class=AssetClass.ETF,
    )

    with pytest.raises(DomainValidationError, match="end date"):
        BacktestRun(
            id=uuid4(),
            strategy_name="Close to next open validation",
            instrument_id=instrument.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 1),
            initial_capital=Decimal("100000"),
            commission=Decimal("0"),
            slippage_bps=Decimal("1"),
            benchmark_symbol="SPY",
        )


def test_trade_exit_must_follow_entry() -> None:
    entry_at = datetime(2025, 1, 3, 14, 30, tzinfo=UTC)

    with pytest.raises(DomainValidationError, match="after entry"):
        Trade(
            id=uuid4(),
            instrument_id=uuid4(),
            entry_order_id=uuid4(),
            exit_order_id=uuid4(),
            entry_at=entry_at,
            entry_price=Price(Decimal("100")),
            quantity=Quantity(Decimal("10")),
            exit_at=entry_at,
            exit_price=Price(Decimal("101")),
        )
