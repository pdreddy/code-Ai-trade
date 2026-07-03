"""Paper broker with deterministic next-open execution semantics."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from backend.app.application.execution import ExecutionPolicy, NextOpenExecutionModel
from backend.app.application.risk import RiskContext, RiskEngine
from backend.app.domain.entities import Bar, Order, Portfolio, PortfolioPosition, RiskRule, Trade
from backend.app.domain.enums import OrderSide, OrderState, OrderType, TimeInForce
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Price, Quantity, RiskFraction


@dataclass(frozen=True, slots=True)
class PaperBrokerConfig:
    portfolio_id: UUID
    name: str
    base_currency: str
    commission: Decimal
    slippage_bps: Decimal


@dataclass(frozen=True, slots=True)
class PaperPosition:
    trade_id: UUID
    instrument_id: UUID
    entry_order_id: UUID
    entry_at: datetime
    entry_price: Price
    quantity: Quantity
    reason: str


@dataclass(slots=True)
class PaperBrokerState:
    cash: Decimal
    pending_orders: list[Order] = field(default_factory=list)
    filled_orders: list[Order] = field(default_factory=list)
    cancelled_orders: list[Order] = field(default_factory=list)
    rejected_orders: list[Order] = field(default_factory=list)
    open_positions: dict[UUID, PaperPosition] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)


class PaperBroker:
    """Stateful paper broker that fills pending market orders on the next bar open."""

    def __init__(
        self,
        config: PaperBrokerConfig,
        state: PaperBrokerState,
        risk_engine: RiskEngine | None = None,
        execution_model: NextOpenExecutionModel | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._risk_engine = risk_engine or RiskEngine()
        self._execution_model = execution_model or NextOpenExecutionModel()

    @property
    def state(self) -> PaperBrokerState:
        return self._state

    def submit_market_order(
        self,
        instrument_id: UUID,
        side: OrderSide,
        quantity: Quantity,
        submitted_at: datetime,
        reason: str,
    ) -> Order:
        if not reason.strip():
            raise DomainValidationError("paper order reason is required")
        order = Order(
            id=uuid4(),
            instrument_id=instrument_id,
            side=side,
            order_type=OrderType.MARKET,
            state=OrderState.PENDING,
            quantity=quantity,
            submitted_at=submitted_at,
            time_in_force=TimeInForce.DAY,
        )
        self._state.pending_orders.append(order)
        return order

    def cancel_order(self, order_id: UUID, cancelled_at: datetime) -> Order:
        for index, order in enumerate(self._state.pending_orders):
            if order.id == order_id:
                if cancelled_at < order.submitted_at:
                    raise DomainValidationError("cancel time cannot precede order submission")
                cancelled = _copy_order(order, state=OrderState.CANCELLED)
                self._state.pending_orders.pop(index)
                self._state.cancelled_orders.append(cancelled)
                return cancelled
        raise DomainValidationError("only pending paper orders can be cancelled")

    def on_bar(
        self,
        bar: Bar,
        risk_rule: RiskRule,
        average_daily_volume: int,
        max_pairwise_correlation: Decimal,
    ) -> None:
        remaining: list[Order] = []
        for order in self._state.pending_orders:
            if order.instrument_id != bar.instrument_id or order.submitted_at >= bar.timestamp:
                remaining.append(order)
                continue
            filled_or_rejected = self._evaluate_and_fill(
                order=order,
                bar=bar,
                risk_rule=risk_rule,
                average_daily_volume=average_daily_volume,
                max_pairwise_correlation=max_pairwise_correlation,
            )
            if filled_or_rejected.state is OrderState.REJECTED:
                self._state.rejected_orders.append(filled_or_rejected)
            else:
                self._state.filled_orders.append(filled_or_rejected)
        self._state.pending_orders = remaining

    def portfolio(self, as_of_bar: Bar) -> Portfolio:
        positions = tuple(
            PortfolioPosition(
                instrument_id=position.instrument_id,
                quantity=position.quantity,
                average_cost=position.entry_price,
                market_price=as_of_bar.close,
                as_of=as_of_bar.timestamp,
            )
            for position in self._state.open_positions.values()
        )
        return Portfolio(
            id=self._config.portfolio_id,
            name=self._config.name,
            base_currency=self._config.base_currency,
            cash=self._state.cash,
            positions=positions,
            as_of=as_of_bar.timestamp,
        )

    def _evaluate_and_fill(
        self,
        order: Order,
        bar: Bar,
        risk_rule: RiskRule,
        average_daily_volume: int,
        max_pairwise_correlation: Decimal,
    ) -> Order:
        policy = ExecutionPolicy(self._config.commission, self._config.slippage_bps)
        fill_price = self._execution_model.fill_price(bar.open, order.side, policy)
        proposed_value = order.quantity.value * fill_price.value
        assessment = self._risk_engine.evaluate(
            RiskContext(
                rule=risk_rule,
                equity=self.portfolio(bar).equity,
                current_gross_exposure=_gross_exposure(self._state.open_positions),
                proposed_order_value=(
                    proposed_value if order.side is OrderSide.BUY else Decimal("0")
                ),
                intended_risk_fraction=RiskFraction(Decimal("0")),
                current_drawdown=RiskFraction(Decimal("0")),
                average_daily_volume=average_daily_volume,
                max_pairwise_correlation=max_pairwise_correlation,
            )
        )
        if not assessment.approved:
            return _reject(order, "; ".join(assessment.reasons))
        if order.side is OrderSide.BUY:
            return self._fill_buy(order, bar, fill_price)
        return self._fill_sell(order, bar, fill_price)

    def _fill_buy(self, order: Order, bar: Bar, fill_price: Price) -> Order:
        total_cost = order.quantity.value * fill_price.value + self._config.commission
        if total_cost > self._state.cash:
            return _reject(order, "insufficient cash")
        if order.instrument_id in self._state.open_positions:
            return _reject(order, "paper broker supports one open long position per instrument")
        filled = _fill(order, bar.timestamp, fill_price)
        self._state.cash -= total_cost
        self._state.open_positions[order.instrument_id] = PaperPosition(
            trade_id=uuid4(),
            instrument_id=order.instrument_id,
            entry_order_id=order.id,
            entry_at=bar.timestamp,
            entry_price=fill_price,
            quantity=order.quantity,
            reason="paper buy filled",
        )
        return filled

    def _fill_sell(self, order: Order, bar: Bar, fill_price: Price) -> Order:
        position = self._state.open_positions.get(order.instrument_id)
        if position is None:
            return _reject(order, "no open position to sell")
        if order.quantity.value > position.quantity.value:
            return _reject(order, "sell quantity exceeds open position")
        filled = _fill(order, bar.timestamp, fill_price)
        self._state.cash += order.quantity.value * fill_price.value - self._config.commission
        self._state.trades.append(
            Trade(
                id=position.trade_id,
                instrument_id=order.instrument_id,
                entry_order_id=position.entry_order_id,
                exit_order_id=order.id,
                entry_at=position.entry_at,
                entry_price=position.entry_price,
                quantity=order.quantity,
                exit_at=bar.timestamp,
                exit_price=fill_price,
                realized_pnl=(fill_price.value - position.entry_price.value) * order.quantity.value
                - (self._config.commission * Decimal("2")),
                reason="paper sell filled",
            )
        )
        del self._state.open_positions[order.instrument_id]
        return filled


def _gross_exposure(positions: dict[UUID, PaperPosition]) -> Decimal:
    return sum(
        (position.quantity.value * position.entry_price.value for position in positions.values()),
        Decimal("0"),
    )


def _fill(order: Order, filled_at: datetime, fill_price: Price) -> Order:
    return Order(
        id=order.id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        state=OrderState.FILLED,
        quantity=order.quantity,
        submitted_at=order.submitted_at,
        time_in_force=order.time_in_force,
        filled_at=filled_at,
        average_fill_price=fill_price,
    )


def _reject(order: Order, reason: str) -> Order:
    return Order(
        id=order.id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        state=OrderState.REJECTED,
        quantity=order.quantity,
        submitted_at=order.submitted_at,
        time_in_force=order.time_in_force,
        rejection_reason=reason,
    )


def _copy_order(order: Order, state: OrderState) -> Order:
    return Order(
        id=order.id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        state=state,
        quantity=order.quantity,
        submitted_at=order.submitted_at,
        time_in_force=order.time_in_force,
    )
