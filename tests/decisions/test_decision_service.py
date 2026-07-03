from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from backend.app.application.decision_engine import MasterDecisionEngine, MasterDecisionRequest
from backend.app.application.decision_service import MasterDecisionService
from backend.app.domain.agents import AgentVote
from backend.app.domain.entities import AgentSignal, MasterDecision
from backend.app.domain.enums import SignalAction
from backend.app.domain.repositories import SignalRepository
from backend.app.domain.value_objects import Confidence, Price


class RecordingSignalRepository(SignalRepository):
    def __init__(self) -> None:
        self.master_decisions: list[MasterDecision] = []

    def save_agent_signal(self, signal: AgentSignal) -> None:
        raise AssertionError("master decision service must not persist independent signals")

    def save_master_decision(self, decision: MasterDecision) -> None:
        self.master_decisions.append(decision)


def test_master_decision_service_persists_generated_decision() -> None:
    signal_at = datetime(2026, 7, 1, 20, tzinfo=UTC)
    vote = AgentVote(
        agent_name="trend",
        action=SignalAction.BUY,
        confidence=Confidence(Decimal("0.75")),
        score=Decimal("0.50"),
        reasons=("close is above rising trend",),
        evaluated_at=signal_at + timedelta(minutes=1),
        signal_bar_timestamp=signal_at,
    )
    repository = RecordingSignalRepository()
    service = MasterDecisionService(MasterDecisionEngine(), repository)

    decision = service.generate_and_persist(
        MasterDecisionRequest(
            instrument_id=uuid4(),
            votes=(vote,),
            current_price=Price(Decimal("100")),
            generated_at=signal_at + timedelta(minutes=2),
        )
    )

    assert repository.master_decisions == [decision]
    assert decision.agent_signal_ids == (vote.id,)
