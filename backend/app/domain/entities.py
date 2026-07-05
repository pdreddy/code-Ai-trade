"""Framework-independent domain entities for the AI Quant research platform."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from backend.app.domain.enums import (
    AssetClass,
    CorporateActionType,
    OrderSide,
    OrderState,
    OrderType,
    SignalAction,
    TimeInForce,
)
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence, Price, Quantity, RiskFraction

ISO_CURRENCY_CODE_LENGTH = 3


@dataclass(frozen=True, slots=True)
class Instrument:
    id: UUID
    symbol: str
    name: str
    exchange: str
    asset_class: AssetClass
    currency: str = "USD"
    active: bool = True

    def __post_init__(self) -> None:
        if not self.symbol.strip().isalnum():
            raise DomainValidationError("instrument symbol must be alphanumeric")
        if not self.exchange.strip():
            raise DomainValidationError("instrument exchange is required")
        if len(self.currency) != ISO_CURRENCY_CODE_LENGTH or not self.currency.isalpha():
            raise DomainValidationError("currency must be a three-letter ISO code")


@dataclass(frozen=True, slots=True)
class Bar:
    instrument_id: UUID
    timestamp: datetime
    open: Price
    high: Price
    low: Price
    close: Price
    volume: int
    adjusted_close: Price | None = None

    def __post_init__(self) -> None:
        if self.volume < 0:
            raise DomainValidationError("bar volume cannot be negative")
        if self.high.value < max(self.open.value, self.close.value, self.low.value):
            raise DomainValidationError(
                "bar high must be greater than or equal to open, low, and close"
            )
        if self.low.value > min(self.open.value, self.close.value, self.high.value):
            raise DomainValidationError(
                "bar low must be less than or equal to open, high, and close"
            )


@dataclass(frozen=True, slots=True)
class CorporateAction:
    instrument_id: UUID
    ex_date: date
    action_type: CorporateActionType
    value: Decimal
    source: str

    def __post_init__(self) -> None:
        if self.value <= Decimal("0"):
            raise DomainValidationError("corporate action value must be positive")
        if not self.source.strip():
            raise DomainValidationError("corporate action source is required")


@dataclass(frozen=True, slots=True)
class AgentSignal:
    id: UUID
    instrument_id: UUID
    agent_name: str
    action: SignalAction
    confidence: Confidence
    score: Decimal
    reasons: tuple[str, ...]
    generated_at: datetime
    signal_bar_timestamp: datetime

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise DomainValidationError("agent name is required")
        if not self.reasons:
            raise DomainValidationError("agent signal must include at least one reason")
        if self.generated_at < self.signal_bar_timestamp:
            raise DomainValidationError("signal generation cannot precede the signal bar")


@dataclass(frozen=True, slots=True)
class MasterDecision:
    id: UUID
    instrument_id: UUID
    action: SignalAction
    confidence: Confidence
    risk_score: RiskFraction
    stop_loss: Price | None
    take_profit: Price | None
    expected_r_multiple: Decimal
    explanation: str
    agent_signal_ids: tuple[UUID, ...]
    generated_at: datetime
    signal_bar_timestamp: datetime

    def __post_init__(self) -> None:
        if not self.explanation.strip():
            raise DomainValidationError("master decision explanation is required")
        if not self.agent_signal_ids:
            raise DomainValidationError("master decision requires at least one agent signal")
        if self.generated_at < self.signal_bar_timestamp:
            raise DomainValidationError("decision generation cannot precede the signal bar")


@dataclass(frozen=True, slots=True)
class Order:
    id: UUID
    instrument_id: UUID
    side: OrderSide
    order_type: OrderType
    state: OrderState
    quantity: Quantity
    submitted_at: datetime
    time_in_force: TimeInForce
    limit_price: Price | None = None
    stop_price: Price | None = None
    filled_at: datetime | None = None
    average_fill_price: Price | None = None
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise DomainValidationError("limit orders require a limit price")
        if self.order_type is OrderType.STOP and self.stop_price is None:
            raise DomainValidationError("stop orders require a stop price")
        if self.state is OrderState.FILLED and (
            self.filled_at is None or self.average_fill_price is None
        ):
            raise DomainValidationError(
                "filled orders require fill timestamp and average fill price"
            )
        if self.state is OrderState.REJECTED and not self.rejection_reason:
            raise DomainValidationError("rejected orders require a rejection reason")


@dataclass(frozen=True, slots=True)
class Trade:
    id: UUID
    instrument_id: UUID
    entry_order_id: UUID
    exit_order_id: UUID | None
    entry_at: datetime
    entry_price: Price
    quantity: Quantity
    exit_at: datetime | None = None
    exit_price: Price | None = None
    realized_pnl: Decimal | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if (self.exit_at is None) != (self.exit_price is None):
            raise DomainValidationError("trade exit timestamp and price must be supplied together")
        if self.exit_at is not None and self.exit_at <= self.entry_at:
            raise DomainValidationError("trade exit must occur after entry")


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    instrument_id: UUID
    quantity: Quantity
    average_cost: Price
    market_price: Price
    as_of: datetime

    @property
    def market_value(self) -> Decimal:
        return self.quantity.value * self.market_price.value

    @property
    def unrealized_pnl(self) -> Decimal:
        return self.quantity.value * (self.market_price.value - self.average_cost.value)


@dataclass(frozen=True, slots=True)
class Portfolio:
    id: UUID
    name: str
    base_currency: str
    cash: Decimal
    positions: tuple[PortfolioPosition, ...]
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("portfolio name is required")
        if len(self.base_currency) != ISO_CURRENCY_CODE_LENGTH or not self.base_currency.isalpha():
            raise DomainValidationError("portfolio base currency must be a three-letter ISO code")

    @property
    def equity(self) -> Decimal:
        return self.cash + sum((position.market_value for position in self.positions), Decimal("0"))


@dataclass(frozen=True, slots=True)
class RiskRule:
    id: UUID
    name: str
    max_risk_per_trade: RiskFraction
    max_gross_exposure: RiskFraction
    max_sector_exposure: RiskFraction
    max_drawdown: RiskFraction
    kill_switch_enabled: bool

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainValidationError("risk rule name is required")


@dataclass(frozen=True, slots=True)
class BacktestRun:
    id: UUID
    strategy_name: str
    instrument_id: UUID
    start_date: date
    end_date: date
    initial_capital: Decimal
    commission: Decimal
    slippage_bps: Decimal
    benchmark_symbol: str

    def __post_init__(self) -> None:
        if self.end_date <= self.start_date:
            raise DomainValidationError("backtest end date must be after start date")
        if self.initial_capital <= Decimal("0"):
            raise DomainValidationError("initial capital must be positive")
        if self.commission < Decimal("0") or self.slippage_bps < Decimal("0"):
            raise DomainValidationError("commission and slippage cannot be negative")
        if not self.benchmark_symbol.strip().isalnum():
            raise DomainValidationError("benchmark symbol must be alphanumeric")
