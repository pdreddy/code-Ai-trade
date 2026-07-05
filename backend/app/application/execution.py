"""Shared deterministic execution semantics for backtests and paper trading."""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from backend.app.domain.enums import OrderSide
from backend.app.domain.value_objects import Price

BASIS_POINTS = Decimal("10000")


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Execution costs used by simulated brokers."""

    commission: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if self.commission < Decimal("0") or self.slippage_bps < Decimal("0"):
            msg = "commission and slippage cannot be negative"
            raise ValueError(msg)


class NextOpenExecutionModel:
    """Price and sizing model shared by backtesting and paper trading."""

    def fill_price(self, open_price: Price, side: OrderSide, policy: ExecutionPolicy) -> Price:
        multiplier = Decimal("1") + policy.slippage_bps / BASIS_POINTS
        if side is OrderSide.SELL:
            multiplier = Decimal("1") - policy.slippage_bps / BASIS_POINTS
        return Price(open_price.value * multiplier)

    def max_buy_quantity(
        self, cash: Decimal, fill_price: Price, policy: ExecutionPolicy
    ) -> Decimal:
        raw_quantity = (cash - policy.commission) / fill_price.value
        return raw_quantity.quantize(Decimal("0.000001"), rounding=ROUND_FLOOR)
