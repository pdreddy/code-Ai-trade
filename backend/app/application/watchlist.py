"""Concurrent lightweight quote+signal summaries for watchlist-style views.

Runs the same AI agents and master-decision engine as the Signals workspace,
but concurrently across many symbols and returning only what a watchlist card
needs (last close, day-over-day change, AI action/confidence) rather than the
full vote payload. Real provider data only; a symbol whose history can't be
fetched surfaces as a per-symbol error rather than being silently dropped or
faked.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
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
from backend.app.domain.providers import HistoricalMarketDataRequest
from backend.app.domain.value_objects import Price

# Mirrors SignalDays' minimum elsewhere: the slowest agent needs ~200 bars of
# trailing history to vote meaningfully.
WATCHLIST_HISTORY_DAYS = 420
MIN_BARS_FOR_CHANGE = 2


@dataclass(frozen=True, slots=True)
class WatchlistQuote:
    symbol: str
    last_close: Decimal
    prior_close: Decimal | None
    change_pct: Decimal | None
    as_of: datetime
    decision: MasterDecision


@dataclass(frozen=True, slots=True)
class WatchlistError:
    symbol: str
    detail: str


@dataclass(slots=True)
class WatchlistService:
    market_data: MarketDataService
    max_workers: int = 12

    def fetch(
        self, symbols: Sequence[str]
    ) -> tuple[tuple[WatchlistQuote, ...], tuple[WatchlistError, ...]]:
        universe = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            outcomes = list(pool.map(self._quote_for, universe))
        quotes = tuple(item for item in outcomes if isinstance(item, WatchlistQuote))
        errors = tuple(item for item in outcomes if isinstance(item, WatchlistError))
        return quotes, errors

    def _quote_for(self, symbol: str) -> WatchlistQuote | WatchlistError:
        try:
            today = datetime.now(UTC).date()
            request = HistoricalMarketDataRequest(
                instrument_id=instrument_id(symbol),
                symbol=symbol,
                start=today - timedelta(days=WATCHLIST_HISTORY_DAYS),
                end=today + timedelta(days=1),
            )
            bars = self.market_data.fetch_daily_history(request).bars
            if not bars:
                return WatchlistError(symbol=symbol, detail="no bars returned by provider")
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
            decision = MasterDecisionEngine().decide(
                MasterDecisionRequest(
                    instrument_id=request.instrument_id,
                    votes=votes,
                    current_price=Price(bars[-1].close.value),
                    generated_at=evaluated_at,
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not sink the watchlist
            return WatchlistError(symbol=symbol, detail=str(exc) or exc.__class__.__name__)

        last_close = bars[-1].close.value
        prior_close = bars[-2].close.value if len(bars) >= MIN_BARS_FOR_CHANGE else None
        change_pct = (
            last_close / prior_close - Decimal("1")
            if prior_close and prior_close > Decimal("0")
            else None
        )
        return WatchlistQuote(
            symbol=symbol,
            last_close=last_close,
            prior_close=prior_close,
            change_pct=change_pct,
            as_of=bars[-1].timestamp,
            decision=decision,
        )
