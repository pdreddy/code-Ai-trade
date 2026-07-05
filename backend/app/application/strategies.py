"""Named, selectable strategy variants built from the existing real agents.

Every variant reuses the same deterministic agents and the same
``MasterDecisionEngine`` aggregation math already proven out across the
platform — a "strategy" here is either a narrower subset of agent votes
(e.g. trend-only) or a stricter ``DecisionPolicy`` threshold (e.g.
high-confidence), never a new, unverified signal source. Each variant's
win rate is whatever its real backtest produces; nothing here targets or
manufactures a specific number.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.backtesting import EventDrivenBacktester
from backend.app.application.decision_engine import DecisionPolicy, MasterDecisionEngine
from backend.app.application.strategy_backtest import StrategyBacktestService

# A stricter score threshold than the platform default (0.25 / -0.25): only
# act when the blended agent vote is strongly directional, trading fewer,
# higher-conviction signals.
HIGH_CONFIDENCE_POLICY = DecisionPolicy(
    buy_threshold=Decimal("0.5"), sell_threshold=Decimal("-0.5")
)


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    key: str
    label: str
    description: str
    # None means every agent's vote is blended (the platform-wide master decision).
    agent_names: tuple[str, ...] | None
    policy: DecisionPolicy


STRATEGIES: tuple[StrategyDefinition, ...] = (
    StrategyDefinition(
        key="master",
        label="Master Decision",
        description=(
            "Every agent's vote blended — the same decision used across the rest of the platform."
        ),
        agent_names=None,
        policy=DecisionPolicy(),
    ),
    StrategyDefinition(
        key="trend_only",
        label="Trend-Only",
        description="Follows only the trend agent's vote; ignores every other signal.",
        agent_names=("trend",),
        policy=DecisionPolicy(),
    ),
    StrategyDefinition(
        key="breakout_only",
        label="Breakout-Only",
        description="Follows only the breakout agent's vote; ignores every other signal.",
        agent_names=("breakout",),
        policy=DecisionPolicy(),
    ),
    StrategyDefinition(
        key="mean_reversion_only",
        label="Mean-Reversion-Only",
        description="Follows only the mean-reversion agent's vote; ignores every other signal.",
        agent_names=("mean_reversion",),
        policy=DecisionPolicy(),
    ),
    StrategyDefinition(
        key="high_confidence",
        label="High-Confidence Consensus",
        description=(
            "The same blended master decision, but only acts when the weighted vote is "
            "strongly directional (±0.5 vs. the platform default of ±0.25) — fewer, "
            "higher-conviction trades."
        ),
        agent_names=None,
        policy=HIGH_CONFIDENCE_POLICY,
    ),
)

STRATEGIES_BY_KEY: dict[str, StrategyDefinition] = {
    strategy.key: strategy for strategy in STRATEGIES
}


def get_strategy(key: str) -> StrategyDefinition:
    try:
        return STRATEGIES_BY_KEY[key]
    except KeyError as exc:
        valid = ", ".join(STRATEGIES_BY_KEY)
        raise ValueError(f"Unknown strategy '{key}'. Valid strategies: {valid}") from exc


def build_strategy_backtest_service(strategy: StrategyDefinition) -> StrategyBacktestService:
    """Construct the backtest service for a named strategy variant."""

    return StrategyBacktestService(
        agents=create_default_agents(),
        engine=MasterDecisionEngine(policy=strategy.policy),
        backtester=EventDrivenBacktester(),
        agent_names=strategy.agent_names,
    )
