"""SQLAlchemy repositories for paper execution and risk audit records."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.application.risk import RiskAssessment
from backend.app.domain.entities import Order, Trade
from backend.app.domain.enums import OrderSide, OrderState, OrderType, TimeInForce
from backend.app.domain.value_objects import Price, Quantity
from backend.app.infrastructure.database.models import (
    PaperOrderModel,
    PaperTradeModel,
    RiskDecisionModel,
)


class SqlAlchemyExecutionRepository:
    """Persist paper orders and trades for auditability."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_order(self, order: Order) -> None:
        model = self._session.get(PaperOrderModel, order.id)
        if model is None:
            model = PaperOrderModel(id=order.id)
            self._session.add(model)
        model.instrument_id = order.instrument_id
        model.side = order.side.value
        model.order_type = order.order_type.value
        model.state = order.state.value
        model.quantity = order.quantity.value
        model.submitted_at = order.submitted_at
        model.time_in_force = order.time_in_force.value
        model.limit_price = order.limit_price.value if order.limit_price else None
        model.stop_price = order.stop_price.value if order.stop_price else None
        model.filled_at = order.filled_at
        model.average_fill_price = (
            order.average_fill_price.value if order.average_fill_price else None
        )
        model.rejection_reason = order.rejection_reason

    def save_trade(self, trade: Trade) -> None:
        model = self._session.get(PaperTradeModel, trade.id)
        if model is None:
            model = PaperTradeModel(id=trade.id)
            self._session.add(model)
        model.instrument_id = trade.instrument_id
        model.entry_order_id = trade.entry_order_id
        model.exit_order_id = trade.exit_order_id
        model.entry_at = trade.entry_at
        model.entry_price = trade.entry_price.value
        model.quantity = trade.quantity.value
        model.exit_at = trade.exit_at
        model.exit_price = trade.exit_price.value if trade.exit_price else None
        model.realized_pnl = trade.realized_pnl
        model.reason = trade.reason


def order_from_model(model: PaperOrderModel) -> Order:
    return Order(
        id=model.id,
        instrument_id=model.instrument_id,
        side=OrderSide(model.side),
        order_type=OrderType(model.order_type),
        state=OrderState(model.state),
        quantity=Quantity(model.quantity),
        submitted_at=model.submitted_at,
        time_in_force=TimeInForce(model.time_in_force),
        limit_price=Price(model.limit_price) if model.limit_price is not None else None,
        stop_price=Price(model.stop_price) if model.stop_price is not None else None,
        filled_at=model.filled_at,
        average_fill_price=Price(model.average_fill_price)
        if model.average_fill_price is not None
        else None,
        rejection_reason=model.rejection_reason,
    )


def trade_from_model(model: PaperTradeModel) -> Trade:
    return Trade(
        id=model.id,
        instrument_id=model.instrument_id,
        entry_order_id=model.entry_order_id,
        exit_order_id=model.exit_order_id,
        entry_at=model.entry_at,
        entry_price=Price(model.entry_price),
        quantity=Quantity(model.quantity),
        exit_at=model.exit_at,
        exit_price=Price(model.exit_price) if model.exit_price is not None else None,
        realized_pnl=model.realized_pnl,
        reason=model.reason,
    )


class SqlAlchemyRiskDecisionRepository:
    """Persist risk approvals/rejections with complete reasons."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_assessment(self, assessment: RiskAssessment, order_id: UUID | None = None) -> None:
        self._session.add(
            RiskDecisionModel(
                order_id=order_id,
                decision=assessment.decision.value,
                reasons="|".join(assessment.reasons),
                created_at_utc=datetime.now(UTC),
            )
        )
