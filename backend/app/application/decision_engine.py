"""Master AI decision aggregation service."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from backend.app.domain.agents import AgentVote
from backend.app.domain.entities import MasterDecision
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence, Price, RiskFraction


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Configuration for deterministic master-decision aggregation."""

    buy_threshold: Decimal = Decimal("0.25")
    sell_threshold: Decimal = Decimal("-0.25")
    stop_loss_fraction: Decimal = Decimal("0.02")
    take_profit_fraction: Decimal = Decimal("0.04")

    def __post_init__(self) -> None:
        if self.buy_threshold <= Decimal("0"):
            raise DomainValidationError("buy threshold must be positive")
        if self.sell_threshold >= Decimal("0"):
            raise DomainValidationError("sell threshold must be negative")
        if self.stop_loss_fraction <= Decimal("0") or self.take_profit_fraction <= Decimal("0"):
            raise DomainValidationError("stop-loss and take-profit fractions must be positive")


@dataclass(frozen=True, slots=True)
class MasterDecisionRequest:
    """Input required to combine independent agent votes."""

    instrument_id: UUID
    votes: Sequence[AgentVote]
    current_price: Price
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.votes:
            raise DomainValidationError("master decision requires at least one agent vote")
        signal_timestamps = {vote.signal_bar_timestamp for vote in self.votes}
        if len(signal_timestamps) != 1:
            raise DomainValidationError("master decision votes must share one signal bar")
        if any(vote.evaluated_at > self.generated_at for vote in self.votes):
            raise DomainValidationError("master decision cannot be generated before source votes")

    @property
    def signal_bar_timestamp(self) -> datetime:
        return self.votes[0].signal_bar_timestamp


class MasterDecisionEngine:
    """Combine independent agent votes into one auditable decision."""

    def __init__(self, policy: DecisionPolicy | None = None) -> None:
        self._policy = policy or DecisionPolicy()

    def decide(self, request: MasterDecisionRequest) -> MasterDecision:
        weighted_score = _weighted_average_score(request.votes)
        action = _action_from_score(weighted_score, self._policy)
        confidence = _confidence_from_votes(request.votes, weighted_score)
        stop_loss, take_profit, expected_r = _trade_levels(
            action=action,
            current_price=request.current_price,
            policy=self._policy,
        )
        return MasterDecision(
            id=uuid4(),
            instrument_id=request.instrument_id,
            action=action,
            confidence=Confidence(confidence),
            risk_score=RiskFraction(Decimal("1") - confidence),
            stop_loss=stop_loss,
            take_profit=take_profit,
            expected_r_multiple=expected_r,
            explanation=_explanation(action, weighted_score, request.votes),
            agent_signal_ids=tuple(vote.id for vote in request.votes),
            generated_at=request.generated_at,
            signal_bar_timestamp=request.signal_bar_timestamp,
        )


def _weighted_average_score(votes: Sequence[AgentVote]) -> Decimal:
    weighted_sum = sum((vote.score * vote.confidence.value for vote in votes), Decimal("0"))
    confidence_sum = sum((vote.confidence.value for vote in votes), Decimal("0"))
    if confidence_sum == Decimal("0"):
        return Decimal("0")
    return weighted_sum / confidence_sum


def _action_from_score(score: Decimal, policy: DecisionPolicy) -> SignalAction:
    if score >= policy.buy_threshold:
        return SignalAction.BUY
    if score <= policy.sell_threshold:
        return SignalAction.SELL
    return SignalAction.HOLD


def _confidence_from_votes(votes: Sequence[AgentVote], score: Decimal) -> Decimal:
    average_confidence = sum((vote.confidence.value for vote in votes), Decimal("0")) / Decimal(
        len(votes)
    )
    directional_strength = min(score.copy_abs(), Decimal("1"))
    return min((average_confidence + directional_strength) / Decimal("2"), Decimal("1"))


def _trade_levels(
    action: SignalAction, current_price: Price, policy: DecisionPolicy
) -> tuple[Price | None, Price | None, Decimal]:
    if action is SignalAction.BUY:
        return (
            Price(current_price.value * (Decimal("1") - policy.stop_loss_fraction)),
            Price(current_price.value * (Decimal("1") + policy.take_profit_fraction)),
            policy.take_profit_fraction / policy.stop_loss_fraction,
        )
    if action is SignalAction.SELL:
        return (
            Price(current_price.value * (Decimal("1") + policy.stop_loss_fraction)),
            Price(current_price.value * (Decimal("1") - policy.take_profit_fraction)),
            policy.take_profit_fraction / policy.stop_loss_fraction,
        )
    return None, None, Decimal("0")


def _explanation(action: SignalAction, score: Decimal, votes: Sequence[AgentVote]) -> str:
    positive = tuple(vote.agent_name for vote in votes if vote.score > Decimal("0"))
    negative = tuple(vote.agent_name for vote in votes if vote.score < Decimal("0"))
    neutral = tuple(vote.agent_name for vote in votes if vote.score == Decimal("0"))
    return (
        f"Master action {action.value.upper()} from weighted score {score:.4f}. "
        f"Positive agents: {', '.join(positive) or 'none'}. "
        f"Negative agents: {', '.join(negative) or 'none'}. "
        f"Neutral agents: {', '.join(neutral) or 'none'}."
    )
