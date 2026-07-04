"""Options research: near-term (0DTE / weekly) contracts, unusual activity, plans.

The service pulls a real option chain, keeps only the near-term expiries that
matter for 0DTE and weekly trading, ranks the unusual options activity (volume
versus open interest), and — using the same AI master decision that drives the
rest of the platform — proposes forward-looking planned option trades aligned
with the signal (calls when the model is bullish, puts when bearish).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import (
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.application.market_data import MarketDataService
from backend.app.application.portfolio_execution import instrument_id
from backend.app.domain.agents import AgentRequest
from backend.app.domain.entities import MasterDecision
from backend.app.domain.enums import SignalAction
from backend.app.domain.options import OptionContract, OptionsProvider, OptionType
from backend.app.domain.providers import HistoricalMarketDataRequest
from backend.app.domain.value_objects import Price

# A weekly horizon: contracts expiring within eight calendar days cover 0DTE through
# the front weekly expiry.
DEFAULT_MAX_DTE = 8
# Unusual activity needs a liquidity floor so a single lotto contract does not top
# the ranking purely on a tiny open-interest base.
MIN_UNUSUAL_VOLUME = 50
SIGNAL_HISTORY_DAYS = 420


@dataclass(frozen=True, slots=True)
class UnusualContract:
    contract: OptionContract
    volume_oi_ratio: Decimal


@dataclass(frozen=True, slots=True)
class PlannedOptionTrade:
    contract: OptionContract
    rationale: str


@dataclass(frozen=True, slots=True)
class OptionsResearch:
    symbol: str
    underlying_price: Decimal
    as_of: str
    signal: MasterDecision
    near_term_count: int
    zero_dte_count: int
    unusual_activity: tuple[UnusualContract, ...]
    planned_trades: tuple[PlannedOptionTrade, ...]


@dataclass(slots=True)
class OptionsResearchService:
    options: OptionsProvider
    market_data: MarketDataService

    def research(
        self, symbol: str, max_dte: int = DEFAULT_MAX_DTE, max_expiries: int = 3
    ) -> OptionsResearch:
        chain = self.options.fetch_option_chain(symbol, max_expiries=max_expiries)
        near_term = tuple(
            contract for contract in chain.contracts if contract.days_to_expiry <= max_dte
        )
        zero_dte = tuple(contract for contract in near_term if contract.days_to_expiry == 0)
        decision = self._signal(symbol)
        unusual = _rank_unusual(near_term)
        planned = _plan_trades(near_term, chain.underlying_price, decision)
        return OptionsResearch(
            symbol=chain.symbol,
            underlying_price=chain.underlying_price,
            as_of=chain.retrieved_at_utc_iso,
            signal=decision,
            near_term_count=len(near_term),
            zero_dte_count=len(zero_dte),
            unusual_activity=unusual,
            planned_trades=planned,
        )

    def _signal(self, symbol: str) -> MasterDecision:
        today = datetime.now(UTC).date()
        request = HistoricalMarketDataRequest(
            instrument_id=instrument_id(symbol),
            symbol=symbol.upper(),
            start=today - timedelta(days=SIGNAL_HISTORY_DAYS),
            end=today + timedelta(days=1),
        )
        bars = self.market_data.fetch_daily_history(request).bars
        evaluated_at = datetime.now(UTC)
        votes = tuple(
            agent.evaluate(
                AgentRequest(
                    instrument_id=request.instrument_id,
                    bars=bars,
                    evaluated_at=evaluated_at,
                )
            )
            for agent in create_default_agents()
        )
        return MasterDecisionEngine().decide(
            MasterDecisionRequest(
                instrument_id=request.instrument_id,
                votes=votes,
                current_price=Price(bars[-1].close.value),
                generated_at=evaluated_at,
            )
        )


def _rank_unusual(contracts: tuple[OptionContract, ...]) -> tuple[UnusualContract, ...]:
    candidates = [
        UnusualContract(contract=contract, volume_oi_ratio=contract.volume_open_interest_ratio)
        for contract in contracts
        if contract.volume >= MIN_UNUSUAL_VOLUME
    ]
    candidates.sort(
        key=lambda item: (item.volume_oi_ratio, item.contract.volume), reverse=True
    )
    return tuple(candidates[:12])


def _plan_trades(
    contracts: tuple[OptionContract, ...],
    underlying_price: Decimal,
    decision: MasterDecision,
) -> tuple[PlannedOptionTrade, ...]:
    if decision.action is SignalAction.HOLD:
        return ()
    wanted = OptionType.CALL if decision.action is SignalAction.BUY else OptionType.PUT
    # Nearest qualifying expiry only — the front-week (or 0DTE) contract is the one
    # the directional signal is actionable on.
    matching = [contract for contract in contracts if contract.option_type is wanted]
    if not matching:
        return ()
    nearest_dte = min(contract.days_to_expiry for contract in matching)
    front = [contract for contract in matching if contract.days_to_expiry == nearest_dte]
    # Rank by proximity to at-the-money, then by liquidity.
    front.sort(
        key=lambda contract: (
            abs(contract.strike - underlying_price),
            -contract.volume,
        )
    )
    direction = "bullish" if wanted is OptionType.CALL else "bearish"
    return tuple(
        PlannedOptionTrade(
            contract=contract,
            rationale=(
                f"AI master decision is {decision.action.value.upper()} "
                f"({(decision.confidence.value * 100):.0f}% confidence) — {direction} "
                f"{wanted.value} {contract.days_to_expiry}DTE near the money."
            ),
        )
        for contract in front[:5]
    )
