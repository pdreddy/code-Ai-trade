"""Application service for generating and persisting master AI decisions."""

from dataclasses import dataclass

from backend.app.application.decision_engine import MasterDecisionEngine, MasterDecisionRequest
from backend.app.domain.entities import MasterDecision
from backend.app.domain.repositories import SignalRepository


@dataclass(slots=True)
class MasterDecisionService:
    """Coordinate deterministic decision aggregation with the signal repository."""

    engine: MasterDecisionEngine
    signal_repository: SignalRepository

    def generate_and_persist(self, request: MasterDecisionRequest) -> MasterDecision:
        """Create a master decision and persist its full vote lineage."""

        decision = self.engine.decide(request)
        self.signal_repository.save_master_decision(decision)
        return decision
