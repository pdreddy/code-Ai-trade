from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.application.decision_engine import (
    DecisionPolicy,
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.domain.agents import AgentVote
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence, Price


def _vote(
    name: str,
    action: SignalAction,
    confidence: str,
    score: str,
    signal_at: datetime,
) -> AgentVote:
    return AgentVote(
        agent_name=name,
        action=action,
        confidence=Confidence(Decimal(confidence)),
        score=Decimal(score),
        reasons=(f"{name} deterministic test reason",),
        evaluated_at=signal_at + timedelta(minutes=1),
        signal_bar_timestamp=signal_at,
    )


def test_master_decision_engine_preserves_source_vote_lineage_and_trade_levels() -> None:
    signal_at = datetime(2026, 7, 1, 20, tzinfo=UTC)
    votes = (
        _vote("trend", SignalAction.BUY, "0.80", "0.60", signal_at),
        _vote("momentum", SignalAction.BUY, "0.70", "0.45", signal_at),
        _vote("risk", SignalAction.HOLD, "0.50", "0.00", signal_at),
    )

    decision = MasterDecisionEngine().decide(
        MasterDecisionRequest(
            instrument_id=uuid4(),
            votes=votes,
            current_price=Price(Decimal("100")),
            generated_at=signal_at + timedelta(minutes=2),
        )
    )

    assert decision.action is SignalAction.BUY
    assert decision.agent_signal_ids == tuple(vote.id for vote in votes)
    assert decision.signal_bar_timestamp == signal_at
    assert decision.stop_loss == Price(Decimal("98.00"))
    assert decision.take_profit == Price(Decimal("104.00"))
    assert decision.expected_r_multiple == Decimal("2")
    assert "Positive agents: trend, momentum" in decision.explanation


def test_master_decision_engine_rejects_mixed_signal_bars() -> None:
    signal_at = datetime(2026, 7, 1, 20, tzinfo=UTC)
    votes = (
        _vote("trend", SignalAction.BUY, "0.80", "0.60", signal_at),
        _vote("momentum", SignalAction.BUY, "0.70", "0.45", signal_at + timedelta(days=1)),
    )

    with pytest.raises(DomainValidationError, match="share one signal bar"):
        MasterDecisionRequest(
            instrument_id=uuid4(),
            votes=votes,
            current_price=Price(Decimal("100")),
            generated_at=signal_at + timedelta(days=1, minutes=2),
        )


def test_decision_policy_requires_directional_thresholds() -> None:
    with pytest.raises(DomainValidationError, match="buy threshold"):
        DecisionPolicy(buy_threshold=Decimal("0"))

    with pytest.raises(DomainValidationError, match="sell threshold"):
        DecisionPolicy(sell_threshold=Decimal("0"))
