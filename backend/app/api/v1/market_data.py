"""Market-data and signal endpoints backed by the real configured provider.

These endpoints fetch live daily history from the configured market-data provider
(Yahoo by default), then run the deterministic research agents and master-decision
engine over that real data. No synthetic prices or signals are generated; when the
provider is unavailable the endpoints surface an honest upstream error.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import (
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.application.market_data import MarketDataService
from backend.app.core.config import Settings, get_settings
from backend.app.domain.agents import AgentRequest, AgentVote
from backend.app.domain.entities import MasterDecision
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import HistoricalMarketData, HistoricalMarketDataRequest
from backend.app.domain.value_objects import Price
from backend.app.infrastructure.providers.factory import create_market_data_provider
from backend.app.infrastructure.providers.yahoo import YahooFinanceProviderError

router = APIRouter(prefix="/market-data", tags=["market-data"])

_INSTRUMENT_NAMESPACE = uuid5(NAMESPACE_URL, "ai-quant-platform/instrument")


def get_market_data_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketDataService:
    """Provide a market-data service bound to the configured provider.

    Exposed as a dependency so tests can override it with an in-memory provider
    instead of reaching the live upstream data source.
    """

    return MarketDataService(create_market_data_provider(settings))


class BarResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None


class MarketDataResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    provider: str
    retrieved_at_utc: str
    bar_count: int
    bars: tuple[BarResponse, ...]


class AgentVoteResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_name: str
    action: str
    confidence: Decimal
    score: Decimal
    reasons: tuple[str, ...]


class MasterDecisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str
    confidence: Decimal
    risk_score: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    expected_r_multiple: Decimal
    explanation: str


class SignalsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    as_of: datetime
    latest_close: Decimal
    bar_count: int
    votes: tuple[AgentVoteResponse, ...]
    master_decision: MasterDecisionResponse


# Upper bound covers ~10 years of calendar days so multi-year research ranges work.
MAX_RANGE_DAYS = 3660
SymbolPath = Annotated[str, Path(min_length=1, max_length=12)]
HistoryDays = Annotated[int, Query(ge=30, le=MAX_RANGE_DAYS)]
SignalDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]


def _instrument_id(symbol: str) -> UUID:
    return uuid5(_INSTRUMENT_NAMESPACE, symbol.upper())


def _history_request(symbol: str, days: int) -> HistoricalMarketDataRequest:
    today = datetime.now(UTC).date()
    try:
        return HistoricalMarketDataRequest(
            instrument_id=_instrument_id(symbol),
            symbol=symbol.upper(),
            start=today - timedelta(days=days),
            end=today + timedelta(days=1),
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch_history(
    service: MarketDataService, request: HistoricalMarketDataRequest
) -> HistoricalMarketData:
    try:
        return service.fetch_daily_history(request)
    except YahooFinanceProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/history", response_model=MarketDataResponse)
def market_data_history(
    symbol: SymbolPath,
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    days: HistoryDays = 180,
) -> MarketDataResponse:
    """Return real daily bars for the requested symbol from the configured provider."""

    request = _history_request(symbol, days)
    data = _fetch_history(service, request)
    bars = tuple(
        BarResponse(
            timestamp=bar.timestamp,
            open=bar.open.value,
            high=bar.high.value,
            low=bar.low.value,
            close=bar.close.value,
            volume=bar.volume,
            adjusted_close=bar.adjusted_close.value if bar.adjusted_close else None,
        )
        for bar in data.bars
    )
    return MarketDataResponse(
        symbol=request.symbol,
        provider=data.lineage.provider,
        retrieved_at_utc=data.lineage.retrieved_at_utc_iso,
        bar_count=len(bars),
        bars=bars,
    )


@router.get("/{symbol}/signals", response_model=SignalsResponse)
def market_data_signals(
    symbol: SymbolPath,
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    days: SignalDays = 420,
) -> SignalsResponse:
    """Compute agent votes and a master decision from real market data."""

    request = _history_request(symbol, days)
    domain_bars = _fetch_history(service, request).bars

    evaluated_at = datetime.now(UTC)
    try:
        agent_request = AgentRequest(
            instrument_id=request.instrument_id,
            bars=domain_bars,
            evaluated_at=evaluated_at,
        )
        votes = tuple(agent.evaluate(agent_request) for agent in create_default_agents())
        decision = MasterDecisionEngine().decide(
            MasterDecisionRequest(
                instrument_id=request.instrument_id,
                votes=votes,
                current_price=Price(domain_bars[-1].close.value),
                generated_at=evaluated_at,
            )
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SignalsResponse(
        symbol=request.symbol,
        as_of=domain_bars[-1].timestamp,
        latest_close=domain_bars[-1].close.value,
        bar_count=len(domain_bars),
        votes=tuple(_vote_response(vote) for vote in votes),
        master_decision=_decision_response(decision),
    )


def _vote_response(vote: AgentVote) -> AgentVoteResponse:
    return AgentVoteResponse(
        agent_name=vote.agent_name,
        action=vote.action.value,
        confidence=vote.confidence.value,
        score=vote.score,
        reasons=vote.reasons,
    )


def _decision_response(decision: MasterDecision) -> MasterDecisionResponse:
    return MasterDecisionResponse(
        action=decision.action.value,
        confidence=decision.confidence.value,
        risk_score=decision.risk_score.value,
        stop_loss=decision.stop_loss.value if decision.stop_loss else None,
        take_profit=decision.take_profit.value if decision.take_profit else None,
        expected_r_multiple=decision.expected_r_multiple,
        explanation=decision.explanation,
    )
