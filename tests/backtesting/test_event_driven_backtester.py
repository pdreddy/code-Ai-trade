from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.app.application.backtesting import (
    BacktestEventType,
    BacktestRequest,
    EventDrivenBacktester,
)
from backend.app.domain.entities import BacktestRun, Bar, MasterDecision
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence, Price, RiskFraction

FILLED_ORDER_COUNT = 2


def _bar(instrument_id: UUID, day: int, open_price: str, close_price: str) -> Bar:
    timestamp = datetime(2026, 1, day, 14, 30, tzinfo=UTC)
    open_value = Decimal(open_price)
    close_value = Decimal(close_price)
    high = max(open_value, close_value) + Decimal("1")
    low = min(open_value, close_value) - Decimal("1")
    return Bar(
        instrument_id=instrument_id,
        timestamp=timestamp,
        open=Price(open_value),
        high=Price(high),
        low=Price(low),
        close=Price(close_value),
        volume=1_000_000,
    )


def _decision(
    instrument_id: UUID,
    action: SignalAction,
    signal_at: datetime,
    explanation: str,
) -> MasterDecision:
    return MasterDecision(
        id=uuid4(),
        instrument_id=instrument_id,
        action=action,
        confidence=Confidence(Decimal("0.75")),
        risk_score=RiskFraction(Decimal("0.25")),
        stop_loss=None,
        take_profit=None,
        expected_r_multiple=Decimal("0"),
        explanation=explanation,
        agent_signal_ids=(uuid4(),),
        generated_at=signal_at + timedelta(minutes=1),
        signal_bar_timestamp=signal_at,
    )


def _run(instrument_id: UUID) -> BacktestRun:
    return BacktestRun(
        id=uuid4(),
        strategy_name="deterministic-master-ai-v1",
        instrument_id=instrument_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 6),
        initial_capital=Decimal("10000"),
        commission=Decimal("1"),
        slippage_bps=Decimal("10"),
        benchmark_symbol="SPY",
    )


def test_backtester_fills_signal_on_next_open_and_never_same_bar() -> None:
    instrument_id = uuid4()
    bars = (
        _bar(instrument_id, 1, "100", "101"),
        _bar(instrument_id, 2, "102", "103"),
        _bar(instrument_id, 3, "104", "105"),
        _bar(instrument_id, 4, "106", "107"),
    )
    decisions = (
        _decision(instrument_id, SignalAction.BUY, bars[0].timestamp, "buy after close"),
        _decision(instrument_id, SignalAction.SELL, bars[2].timestamp, "sell after close"),
    )

    result = EventDrivenBacktester().run(
        BacktestRequest(run=_run(instrument_id), bars=bars, decisions=decisions)
    )

    assert len(result.orders) == FILLED_ORDER_COUNT
    assert result.orders[0].submitted_at == bars[0].timestamp
    assert result.orders[0].filled_at == bars[1].timestamp
    assert result.orders[0].average_fill_price == Price(Decimal("102.102"))
    assert result.orders[1].submitted_at == bars[2].timestamp
    assert result.orders[1].filled_at == bars[3].timestamp
    assert result.orders[1].average_fill_price == Price(Decimal("105.894"))
    assert all(order.filled_at != order.submitted_at for order in result.orders)
    assert result.trades[0].trade.entry_at == bars[1].timestamp
    assert result.trades[0].trade.exit_at == bars[3].timestamp
    assert result.metrics.trade_count == 1
    assert result.metrics.exposure == Decimal("0.5")
    assert BacktestEventType.SIGNAL in {event.event_type for event in result.event_log}
    assert BacktestEventType.FILL in {event.event_type for event in result.event_log}


def test_backtester_rejects_decision_without_matching_signal_bar() -> None:
    instrument_id = uuid4()
    bars = (_bar(instrument_id, 1, "100", "101"), _bar(instrument_id, 2, "102", "103"))
    missing_bar_time = datetime(2026, 1, 3, 14, 30, tzinfo=UTC)

    with pytest.raises(DomainValidationError, match="available signal bar"):
        BacktestRequest(
            run=_run(instrument_id),
            bars=bars,
            decisions=(
                _decision(instrument_id, SignalAction.BUY, missing_bar_time, "missing bar"),
            ),
        )


def test_backtester_rejects_duplicate_decisions_for_one_signal_bar() -> None:
    instrument_id = uuid4()
    bars = (_bar(instrument_id, 1, "100", "101"), _bar(instrument_id, 2, "102", "103"))
    decisions = (
        _decision(instrument_id, SignalAction.BUY, bars[0].timestamp, "first"),
        _decision(instrument_id, SignalAction.HOLD, bars[0].timestamp, "duplicate"),
    )

    with pytest.raises(DomainValidationError, match="only one master decision"):
        EventDrivenBacktester().run(
            BacktestRequest(run=_run(instrument_id), bars=bars, decisions=decisions)
        )
