"""Compose agents, the master-decision engine, and the backtester into one system.

For each historical bar the independent agents vote, the votes aggregate into a
deterministic master decision, and the event-driven backtester executes those
decisions (signal-on-close, fill-next-open). The result is an auditable track
record plus the latest decision, which is the forward-looking signal.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.application.backtesting import (
    BacktestRequest,
    BacktestResult,
    EventDrivenBacktester,
)
from backend.app.application.decision_engine import (
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.domain.agents import AgentRequest, TradingAgent
from backend.app.domain.entities import BacktestRun, Bar, MasterDecision
from backend.app.domain.value_objects import Price

# The most history-hungry agent looks back 200 bars, so a bounded trailing window
# yields identical votes to the full history while keeping multi-year runs linear.
AGENT_LOOKBACK_BARS = 220


@dataclass(frozen=True, slots=True)
class StrategyBacktestResult:
    result: BacktestResult
    latest_decision: MasterDecision | None


@dataclass(slots=True)
class StrategyBacktestService:
    agents: tuple[TradingAgent, ...]
    engine: MasterDecisionEngine
    backtester: EventDrivenBacktester

    def run(self, run: BacktestRun, bars: Sequence[Bar]) -> StrategyBacktestResult:
        decisions = tuple(self._decide_at(run, bars, index) for index in range(len(bars)))
        request = BacktestRequest(run=run, bars=bars, decisions=decisions)
        result = self.backtester.run(request)
        return StrategyBacktestResult(
            result=result,
            latest_decision=decisions[-1] if decisions else None,
        )

    def _decide_at(
        self, run: BacktestRun, bars: Sequence[Bar], index: int
    ) -> MasterDecision:
        window_start = max(0, index + 1 - AGENT_LOOKBACK_BARS)
        window = bars[window_start : index + 1]
        evaluated_at = bars[index].timestamp
        agent_request = AgentRequest(
            instrument_id=run.instrument_id,
            bars=window,
            evaluated_at=evaluated_at,
        )
        votes = tuple(agent.evaluate(agent_request) for agent in self.agents)
        return self.engine.decide(
            MasterDecisionRequest(
                instrument_id=run.instrument_id,
                votes=votes,
                current_price=Price(bars[index].close.value),
                generated_at=evaluated_at,
            )
        )
