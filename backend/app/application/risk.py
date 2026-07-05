"""Deterministic pre-trade risk engine for research and paper trading."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.app.domain.entities import RiskRule
from backend.app.domain.value_objects import RiskFraction


class RiskDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Non-portfolio risk limits not present in the base risk-rule entity."""

    min_average_daily_volume: int = 250_000
    max_correlation: Decimal = Decimal("0.85")

    def __post_init__(self) -> None:
        if self.min_average_daily_volume < 0:
            msg = "minimum average daily volume cannot be negative"
            raise ValueError(msg)
        if not Decimal("0") <= self.max_correlation <= Decimal("1"):
            msg = "maximum correlation must be between 0 and 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RiskContext:
    """Inputs required to evaluate one proposed order."""

    rule: RiskRule
    equity: Decimal
    current_gross_exposure: Decimal
    proposed_order_value: Decimal
    intended_risk_fraction: RiskFraction
    current_drawdown: RiskFraction
    average_daily_volume: int
    max_pairwise_correlation: Decimal

    def __post_init__(self) -> None:
        if self.equity <= Decimal("0"):
            msg = "risk context equity must be positive"
            raise ValueError(msg)
        if self.current_gross_exposure < Decimal("0") or self.proposed_order_value < Decimal("0"):
            msg = "risk exposure values cannot be negative"
            raise ValueError(msg)
        if self.average_daily_volume < 0:
            msg = "average daily volume cannot be negative"
            raise ValueError(msg)
        if not Decimal("0") <= self.max_pairwise_correlation <= Decimal("1"):
            msg = "correlation must be between 0 and 1"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    decision: RiskDecision
    reasons: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return self.decision is RiskDecision.APPROVED


class RiskEngine:
    """Evaluate pre-trade portfolio, drawdown, liquidity, and correlation limits."""

    def __init__(self, policy: RiskPolicy | None = None) -> None:
        self._policy = policy or RiskPolicy()

    def evaluate(self, context: RiskContext) -> RiskAssessment:
        reasons: list[str] = []
        if context.rule.kill_switch_enabled:
            reasons.append("kill switch is enabled")
        if context.intended_risk_fraction.value > context.rule.max_risk_per_trade.value:
            reasons.append("max risk per trade exceeded")
        projected_exposure = (
            context.current_gross_exposure + context.proposed_order_value
        ) / context.equity
        if projected_exposure > context.rule.max_gross_exposure.value:
            reasons.append("max gross exposure exceeded")
        if context.current_drawdown.value > context.rule.max_drawdown.value:
            reasons.append("max drawdown exceeded")
        if context.average_daily_volume < self._policy.min_average_daily_volume:
            reasons.append("liquidity filter failed")
        if context.max_pairwise_correlation > self._policy.max_correlation:
            reasons.append("correlation filter failed")
        if reasons:
            return RiskAssessment(RiskDecision.REJECTED, tuple(reasons))
        return RiskAssessment(RiskDecision.APPROVED, ("risk checks passed",))
