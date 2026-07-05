from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from backend.app.application.paper_trading import PaperBroker, PaperBrokerConfig, PaperBrokerState
from backend.app.domain.entities import Bar, RiskRule
from backend.app.domain.enums import OrderSide, OrderState
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Price, Quantity, RiskFraction


def _bar(instrument_id: UUID, day: int, open_price: str, close_price: str) -> Bar:
    open_value = Decimal(open_price)
    close_value = Decimal(close_price)
    return Bar(
        instrument_id=instrument_id,
        timestamp=datetime(2026, 7, day, 13, 30, tzinfo=UTC),
        open=Price(open_value),
        high=Price(max(open_value, close_value) + Decimal("1")),
        low=Price(min(open_value, close_value) - Decimal("1")),
        close=Price(close_value),
        volume=2_000_000,
    )


def _risk_rule(kill_switch: bool = False) -> RiskRule:
    return RiskRule(
        id=uuid4(),
        name="paper-default",
        max_risk_per_trade=RiskFraction(Decimal("0.02")),
        max_gross_exposure=RiskFraction(Decimal("1")),
        max_sector_exposure=RiskFraction(Decimal("0.50")),
        max_drawdown=RiskFraction(Decimal("0.20")),
        kill_switch_enabled=kill_switch,
    )


def _broker() -> PaperBroker:
    return PaperBroker(
        PaperBrokerConfig(
            portfolio_id=uuid4(),
            name="paper",
            base_currency="USD",
            commission=Decimal("1"),
            slippage_bps=Decimal("10"),
        ),
        PaperBrokerState(cash=Decimal("10000")),
    )


def test_paper_broker_pending_fill_and_trade_lifecycle_uses_next_open() -> None:
    instrument_id = uuid4()
    broker = _broker()
    first_bar = _bar(instrument_id, 1, "100", "101")
    second_bar = _bar(instrument_id, 2, "102", "103")
    third_bar = _bar(instrument_id, 3, "104", "105")

    buy = broker.submit_market_order(
        instrument_id, OrderSide.BUY, Quantity(Decimal("10")), first_bar.timestamp, "buy"
    )
    broker.on_bar(first_bar, _risk_rule(), 1_000_000, Decimal("0.20"))
    assert broker.state.pending_orders == [buy]

    broker.on_bar(second_bar, _risk_rule(), 1_000_000, Decimal("0.20"))
    assert broker.state.filled_orders[0].state is OrderState.FILLED
    assert broker.state.filled_orders[0].filled_at == second_bar.timestamp
    assert broker.state.filled_orders[0].average_fill_price == Price(Decimal("102.102"))

    broker.submit_market_order(
        instrument_id, OrderSide.SELL, Quantity(Decimal("10")), second_bar.timestamp, "sell"
    )
    broker.on_bar(third_bar, _risk_rule(), 1_000_000, Decimal("0.20"))

    assert len(broker.state.trades) == 1
    assert broker.state.trades[0].entry_at == second_bar.timestamp
    assert broker.state.trades[0].exit_at == third_bar.timestamp
    assert not broker.state.open_positions


def test_paper_broker_cancel_pending_order() -> None:
    instrument_id = uuid4()
    broker = _broker()
    bar = _bar(instrument_id, 1, "100", "101")
    order = broker.submit_market_order(
        instrument_id, OrderSide.BUY, Quantity(Decimal("1")), bar.timestamp, "cancel me"
    )

    cancelled = broker.cancel_order(order.id, bar.timestamp)

    assert cancelled.state is OrderState.CANCELLED
    assert broker.state.pending_orders == []
    assert broker.state.cancelled_orders == [cancelled]


def test_paper_broker_rejects_order_when_risk_engine_rejects() -> None:
    instrument_id = uuid4()
    broker = _broker()
    first_bar = _bar(instrument_id, 1, "100", "101")
    second_bar = _bar(instrument_id, 2, "102", "103")
    broker.submit_market_order(
        instrument_id, OrderSide.BUY, Quantity(Decimal("1")), first_bar.timestamp, "blocked"
    )

    broker.on_bar(second_bar, _risk_rule(kill_switch=True), 1_000_000, Decimal("0.20"))

    assert broker.state.rejected_orders[0].state is OrderState.REJECTED
    rejection_reason = broker.state.rejected_orders[0].rejection_reason
    assert rejection_reason is not None
    assert "kill switch" in rejection_reason


def test_paper_broker_requires_order_reason() -> None:
    with pytest.raises(DomainValidationError, match="reason"):
        _broker().submit_market_order(
            uuid4(), OrderSide.BUY, Quantity(Decimal("1")), datetime.now(UTC), ""
        )
