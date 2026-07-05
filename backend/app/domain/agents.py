"""Domain contracts for independent trading research agents."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from backend.app.domain.entities import Bar, PortfolioPosition, RiskRule
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """Immutable input supplied to independent market research agents."""

    instrument_id: UUID
    bars: Sequence[Bar]
    evaluated_at: datetime
    portfolio_position: PortfolioPosition | None = None
    risk_rule: RiskRule | None = None

    def __post_init__(self) -> None:
        if not self.bars:
            raise DomainValidationError("agent request requires at least one bar")
        timestamps = tuple(bar.timestamp for bar in self.bars)
        if timestamps != tuple(sorted(timestamps)):
            raise DomainValidationError("agent request bars must be sorted by timestamp")
        if timestamps[-1] > self.evaluated_at:
            raise DomainValidationError("agent request cannot include future bars")
        if any(bar.instrument_id != self.instrument_id for bar in self.bars):
            raise DomainValidationError("agent request bars must match the requested instrument")

    @property
    def signal_bar_timestamp(self) -> datetime:
        """Timestamp of the last bar available to the agent."""

        return self.bars[-1].timestamp


@dataclass(frozen=True, slots=True)
class AgentVote:
    """Standardized output from one independent research agent."""

    agent_name: str
    action: SignalAction
    confidence: Confidence
    score: Decimal
    reasons: tuple[str, ...]
    evaluated_at: datetime
    signal_bar_timestamp: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise DomainValidationError("agent vote requires an agent name")
        if not self.reasons:
            raise DomainValidationError("agent vote requires at least one reason")
        if self.evaluated_at < self.signal_bar_timestamp:
            raise DomainValidationError("agent vote evaluation cannot precede the signal bar")


class TradingAgent(Protocol):
    """Protocol implemented by all independent research agents."""

    name: str

    def evaluate(self, request: AgentRequest) -> AgentVote: ...
