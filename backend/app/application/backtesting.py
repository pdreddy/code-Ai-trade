"""Event-driven backtesting engine with signal-close / next-open execution semantics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from backend.app.domain.entities import BacktestRun, Bar, MasterDecision, Order, Trade
from backend.app.domain.enums import OrderSide, OrderState, OrderType, SignalAction, TimeInForce
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Price, Quantity

TRADING_DAYS_PER_YEAR = Decimal("252")
BASIS_POINTS = Decimal("10000")
MIN_SAMPLE_SIZE = 2


class BacktestEventType(StrEnum):
    MARKET = "market"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    PORTFOLIO = "portfolio"


@dataclass(frozen=True, slots=True)
class BacktestEvent:
    timestamp: datetime
    event_type: BacktestEventType
    description: str


@dataclass(frozen=True, slots=True)
class EquityPoint:
    timestamp: datetime
    equity: Decimal


@dataclass(frozen=True, slots=True)
class DrawdownPoint:
    timestamp: datetime
    drawdown: Decimal


@dataclass(frozen=True, slots=True)
class MonthlyReturn:
    month: date
    return_fraction: Decimal


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    trade: Trade
    entry_reason: str
    exit_reason: str | None


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    cagr: Decimal
    sharpe: Decimal
    sortino: Decimal
    calmar: Decimal
    profit_factor: Decimal
    win_rate: Decimal
    trade_count: int
    max_drawdown: Decimal
    exposure: Decimal
    benchmark_return: Decimal | None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    run: BacktestRun
    orders: tuple[Order, ...]
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    drawdown_curve: tuple[DrawdownPoint, ...]
    monthly_returns: tuple[MonthlyReturn, ...]
    metrics: BacktestMetrics
    event_log: tuple[BacktestEvent, ...]


@dataclass(frozen=True, slots=True)
class BacktestRequest:
    run: BacktestRun
    bars: Sequence[Bar]
    decisions: Sequence[MasterDecision]
    benchmark_bars: Sequence[Bar] = ()

    def __post_init__(self) -> None:
        if not self.bars:
            raise DomainValidationError("backtest requires at least one bar")
        timestamps = tuple(bar.timestamp for bar in self.bars)
        if timestamps != tuple(sorted(timestamps)):
            raise DomainValidationError("backtest bars must be sorted by timestamp")
        if any(bar.instrument_id != self.run.instrument_id for bar in self.bars):
            raise DomainValidationError("backtest bars must match run instrument")
        start = self.run.start_date
        end = self.run.end_date
        if any(not start <= bar.timestamp.date() <= end for bar in self.bars):
            raise DomainValidationError("backtest bars must be inside run date range")
        if any(
            decision.instrument_id != self.run.instrument_id for decision in self.decisions
        ):
            raise DomainValidationError("backtest decisions must match run instrument")
        bar_timestamps = set(timestamps)
        if any(
            decision.signal_bar_timestamp not in bar_timestamps
            for decision in self.decisions
        ):
            raise DomainValidationError("every decision must reference an available signal bar")
        if any(
            decision.generated_at < decision.signal_bar_timestamp
            for decision in self.decisions
        ):
            raise DomainValidationError("decision generation cannot precede signal bar")


@dataclass(slots=True)
class _OpenPosition:
    trade_id: UUID
    entry_order_id: UUID
    entry_at: datetime
    entry_price: Price
    quantity: Quantity
    entry_reason: str


@dataclass(frozen=True, slots=True)
class _PendingOrder:
    decision: MasterDecision
    side: OrderSide
    submitted_at: datetime


class EventDrivenBacktester:
    """Long-only event-driven backtester that fills signals on the next bar open."""

    def run(self, request: BacktestRequest) -> BacktestResult:
        decisions_by_signal_bar = _index_decisions(request.decisions)
        cash = request.run.initial_capital
        position: _OpenPosition | None = None
        pending_order: _PendingOrder | None = None
        orders: list[Order] = []
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        event_log: list[BacktestEvent] = []
        exposed_bars = 0

        for index, bar in enumerate(request.bars):
            event_log.append(
                BacktestEvent(bar.timestamp, BacktestEventType.MARKET, "market bar open")
            )
            if pending_order is not None:
                cash, position = self._fill_pending_order(
                    pending_order=pending_order,
                    bar=bar,
                    run=request.run,
                    cash=cash,
                    position=position,
                    orders=orders,
                    trades=trades,
                    event_log=event_log,
                )
                pending_order = None

            if position is not None:
                exposed_bars += 1
            equity_curve.append(EquityPoint(bar.timestamp, _equity(cash, position, bar.close)))
            event_log.append(
                BacktestEvent(
                    bar.timestamp, BacktestEventType.PORTFOLIO, "portfolio marked at close"
                )
            )

            decision = decisions_by_signal_bar.get(bar.timestamp)
            if decision is not None and index < len(request.bars) - 1:
                event_log.append(
                    BacktestEvent(bar.timestamp, BacktestEventType.SIGNAL, decision.explanation)
                )
                pending_order = _order_from_decision(decision, position)
                if pending_order is not None:
                    event_log.append(
                        BacktestEvent(
                            bar.timestamp,
                            BacktestEventType.ORDER,
                            f"submitted {pending_order.side.value} market order for next open",
                        )
                    )

        drawdown_curve = _drawdowns(equity_curve)
        monthly_returns = _monthly_returns(equity_curve)
        metrics = _metrics(
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades,
            exposed_bars=exposed_bars,
            total_bars=len(request.bars),
            benchmark_bars=request.benchmark_bars,
        )
        return BacktestResult(
            run=request.run,
            orders=tuple(orders),
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            drawdown_curve=tuple(drawdown_curve),
            monthly_returns=tuple(monthly_returns),
            metrics=metrics,
            event_log=tuple(event_log),
        )

    def _fill_pending_order(
        self,
        pending_order: _PendingOrder,
        bar: Bar,
        run: BacktestRun,
        cash: Decimal,
        position: _OpenPosition | None,
        orders: list[Order],
        trades: list[BacktestTrade],
        event_log: list[BacktestEvent],
    ) -> tuple[Decimal, _OpenPosition | None]:
        if pending_order.submitted_at >= bar.timestamp:
            raise DomainValidationError("pending order cannot fill on the signal bar")
        fill_price = _slipped_open(bar.open, pending_order.side, run.slippage_bps)
        order_id = uuid4()
        order = Order(
            id=order_id,
            instrument_id=run.instrument_id,
            side=pending_order.side,
            order_type=OrderType.MARKET,
            state=OrderState.FILLED,
            quantity=Quantity(Decimal("1")),
            submitted_at=pending_order.submitted_at,
            time_in_force=TimeInForce.DAY,
            filled_at=bar.timestamp,
            average_fill_price=fill_price,
        )

        if pending_order.side is OrderSide.BUY and position is None:
            quantity = _buy_quantity(cash, fill_price.value, run.commission)
            if quantity <= Decimal("0"):
                rejected = _rejected_order(order, "insufficient cash for next-open fill")
                orders.append(rejected)
                event_log.append(
                    BacktestEvent(
                        bar.timestamp,
                        BacktestEventType.ORDER,
                        rejected.rejection_reason or "order rejected",
                    )
                )
                return cash, position
            filled_order = _replace_order_quantity(order, Quantity(quantity))
            orders.append(filled_order)
            event_log.append(
                BacktestEvent(bar.timestamp, BacktestEventType.FILL, "buy filled at next open")
            )
            cash -= quantity * fill_price.value + run.commission
            return cash, _OpenPosition(
                trade_id=uuid4(),
                entry_order_id=order_id,
                entry_at=bar.timestamp,
                entry_price=fill_price,
                quantity=Quantity(quantity),
                entry_reason=pending_order.decision.explanation,
            )

        if pending_order.side is OrderSide.SELL and position is not None:
            filled_order = _replace_order_quantity(order, position.quantity)
            orders.append(filled_order)
            event_log.append(
                BacktestEvent(bar.timestamp, BacktestEventType.FILL, "sell filled at next open")
            )
            cash += position.quantity.value * fill_price.value - run.commission
            trade = Trade(
                id=position.trade_id,
                instrument_id=run.instrument_id,
                entry_order_id=position.entry_order_id,
                exit_order_id=order_id,
                entry_at=position.entry_at,
                entry_price=position.entry_price,
                quantity=position.quantity,
                exit_at=bar.timestamp,
                exit_price=fill_price,
                realized_pnl=(
                    (fill_price.value - position.entry_price.value) * position.quantity.value
                )
                - (run.commission * Decimal("2")),
                reason=pending_order.decision.explanation,
            )
            trades.append(
                BacktestTrade(
                    trade=trade,
                    entry_reason=position.entry_reason,
                    exit_reason=pending_order.decision.explanation,
                )
            )
            return cash, None

        return cash, position


def _index_decisions(decisions: Sequence[MasterDecision]) -> Mapping[datetime, MasterDecision]:
    indexed: dict[datetime, MasterDecision] = {}
    for decision in decisions:
        if decision.signal_bar_timestamp in indexed:
            raise DomainValidationError("only one master decision is allowed per signal bar")
        indexed[decision.signal_bar_timestamp] = decision
    return indexed


def _order_from_decision(
    decision: MasterDecision, position: _OpenPosition | None
) -> _PendingOrder | None:
    if decision.action is SignalAction.BUY and position is None:
        return _PendingOrder(decision, OrderSide.BUY, decision.signal_bar_timestamp)
    if decision.action is SignalAction.SELL and position is not None:
        return _PendingOrder(decision, OrderSide.SELL, decision.signal_bar_timestamp)
    return None


def _slipped_open(open_price: Price, side: OrderSide, slippage_bps: Decimal) -> Price:
    multiplier = Decimal("1") + slippage_bps / BASIS_POINTS
    if side is OrderSide.SELL:
        multiplier = Decimal("1") - slippage_bps / BASIS_POINTS
    return Price(open_price.value * multiplier)


def _buy_quantity(cash: Decimal, price: Decimal, commission: Decimal) -> Decimal:
    raw_quantity = (cash - commission) / price
    return raw_quantity.quantize(Decimal("0.000001"), rounding=ROUND_FLOOR)


def _replace_order_quantity(order: Order, quantity: Quantity) -> Order:
    return Order(
        id=order.id,
        instrument_id=order.instrument_id,
        side=order.side,
        order_type=order.order_type,
        state=order.state,
        quantity=quantity,
        submitted_at=order.submitted_at,
        time_in_force=order.time_in_force,
        filled_at=order.filled_at,
        average_fill_price=order.average_fill_price,
    )


def _rejected_order(order: Order, reason: str) -> Order:
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


def _equity(cash: Decimal, position: _OpenPosition | None, close: Price) -> Decimal:
    if position is None:
        return cash
    return cash + position.quantity.value * close.value


def _drawdowns(equity_curve: Sequence[EquityPoint]) -> list[DrawdownPoint]:
    high_watermark = equity_curve[0].equity
    drawdowns: list[DrawdownPoint] = []
    for point in equity_curve:
        high_watermark = max(high_watermark, point.equity)
        drawdown = (
            Decimal("0")
            if high_watermark == Decimal("0")
            else point.equity / high_watermark - 1
        )
        drawdowns.append(DrawdownPoint(point.timestamp, drawdown))
    return drawdowns


def _monthly_returns(equity_curve: Sequence[EquityPoint]) -> list[MonthlyReturn]:
    first_by_month: dict[date, Decimal] = {}
    last_by_month: dict[date, Decimal] = {}
    for point in equity_curve:
        month = date(point.timestamp.year, point.timestamp.month, 1)
        first_by_month.setdefault(month, point.equity)
        last_by_month[month] = point.equity
    return [
        MonthlyReturn(month, last_by_month[month] / first_by_month[month] - 1)
        for month in sorted(first_by_month)
        if first_by_month[month] != Decimal("0")
    ]


def _metrics(
    equity_curve: Sequence[EquityPoint],
    drawdown_curve: Sequence[DrawdownPoint],
    trades: Sequence[BacktestTrade],
    exposed_bars: int,
    total_bars: int,
    benchmark_bars: Sequence[Bar],
) -> BacktestMetrics:
    start_equity = equity_curve[0].equity
    end_equity = equity_curve[-1].equity
    periods = Decimal(max(len(equity_curve) - 1, 1))
    total_return = (
        end_equity / start_equity - 1 if start_equity != Decimal("0") else Decimal("0")
    )
    cagr = Decimal(
        str((float(end_equity / start_equity) ** float(TRADING_DAYS_PER_YEAR / periods)) - 1)
    )
    returns = _period_returns(equity_curve)
    max_drawdown = min((point.drawdown for point in drawdown_curve), default=Decimal("0"))
    realized_pnls = tuple(
        trade.trade.realized_pnl
        for trade in trades
        if trade.trade.realized_pnl is not None
    )
    positive_pnl = sum((pnl for pnl in realized_pnls if pnl > Decimal("0")), Decimal("0"))
    negative_pnl = sum(
        (
            pnl.copy_abs()
            for pnl in realized_pnls
            if pnl < Decimal("0")
        ),
        Decimal("0"),
    )
    wins = sum(1 for pnl in realized_pnls if pnl > Decimal("0"))
    return BacktestMetrics(
        cagr=cagr,
        sharpe=_sharpe(returns),
        sortino=_sortino(returns),
        calmar=(
            Decimal("0") if max_drawdown == Decimal("0") else cagr / max_drawdown.copy_abs()
        ),
        profit_factor=(
            positive_pnl / negative_pnl if negative_pnl > Decimal("0") else positive_pnl
        ),
        win_rate=Decimal(wins) / Decimal(len(trades)) if trades else Decimal("0"),
        trade_count=len(trades),
        max_drawdown=max_drawdown,
        exposure=Decimal(exposed_bars) / Decimal(total_bars),
        benchmark_return=_benchmark_return(benchmark_bars) if benchmark_bars else total_return,
    )


def _period_returns(equity_curve: Sequence[EquityPoint]) -> tuple[Decimal, ...]:
    returns: list[Decimal] = []
    for previous, current in zip(equity_curve, equity_curve[1:], strict=False):
        if previous.equity != Decimal("0"):
            returns.append(current.equity / previous.equity - 1)
    return tuple(returns)


def _sharpe(returns: Sequence[Decimal]) -> Decimal:
    if len(returns) < MIN_SAMPLE_SIZE:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    std = _stddev(returns, mean)
    if std == 0:
        return Decimal("0")
    return Decimal(str(float(mean / std) * math.sqrt(float(TRADING_DAYS_PER_YEAR))))


def _sortino(returns: Sequence[Decimal]) -> Decimal:
    downside = tuple(ret for ret in returns if ret < Decimal("0"))
    if len(downside) < MIN_SAMPLE_SIZE:
        return Decimal("0")
    mean = sum(returns, Decimal("0")) / Decimal(len(returns))
    downside_std = _stddev(downside, Decimal("0"))
    if downside_std == 0:
        return Decimal("0")
    return Decimal(str(float(mean / downside_std) * math.sqrt(float(TRADING_DAYS_PER_YEAR))))


def _stddev(values: Sequence[Decimal], mean: Decimal) -> Decimal:
    variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(
        len(values) - 1
    )
    return Decimal(str(math.sqrt(float(variance))))


def _benchmark_return(benchmark_bars: Sequence[Bar]) -> Decimal:
    if len(benchmark_bars) < MIN_SAMPLE_SIZE:
        return Decimal("0")
    start = benchmark_bars[0].close.value
    end = benchmark_bars[-1].close.value
    return end / start - 1
