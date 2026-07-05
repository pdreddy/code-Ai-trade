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
from backend.app.application.backtesting import BacktestResult
from backend.app.application.decision_engine import (
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.application.market_data import MarketDataService
from backend.app.application.strategies import (
    STRATEGIES,
    build_strategy_backtest_service,
    get_strategy,
)
from backend.app.application.strategy_screener import StrategyScreen, StrategyScreenerService
from backend.app.core.config import Settings, get_settings
from backend.app.domain.agents import AgentRequest, AgentVote
from backend.app.domain.entities import BacktestRun, MasterDecision
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


class TradeRecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_at: datetime
    entry_price: Decimal
    exit_at: datetime | None
    exit_price: Decimal | None
    quantity: Decimal
    realized_pnl: Decimal | None
    entry_reason: str
    exit_reason: str | None


class EquityPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    equity: Decimal


class BacktestMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    success_rate: Decimal
    total_return: Decimal
    cagr: Decimal
    sharpe: Decimal
    sortino: Decimal
    calmar: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    exposure: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int


class BacktestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    strategy: str
    start: datetime
    end: datetime
    bar_count: int
    initial_capital: Decimal
    final_equity: Decimal
    metrics: BacktestMetricsResponse
    equity_curve: tuple[EquityPointResponse, ...]
    trades: tuple[TradeRecordResponse, ...]
    next_signal: MasterDecisionResponse | None


class StrategyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str


BacktestDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]


@router.get("/{symbol}/backtest", response_model=BacktestResponse)
def market_data_backtest(
    symbol: SymbolPath,
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    days: BacktestDays = 1825,
    capital: Annotated[Decimal, Query(gt=0)] = Decimal("10000"),
    strategy: str = "master",
) -> BacktestResponse:
    """Execute a named AI strategy over real history and report the proven track record.

    Every bar produces a master decision; the event-driven backtester fills those
    decisions on the next open. The response is the executed trade list, the equity
    curve, performance metrics (including the win/success rate), and the latest
    decision, which is the forward-looking signal. See /market-data/strategies for
    the list of selectable strategy variants.
    """

    try:
        strategy_definition = get_strategy(strategy)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request = _history_request(symbol, days)
    domain_bars = _fetch_history(service, request).bars

    try:
        run = BacktestRun(
            id=uuid5(_INSTRUMENT_NAMESPACE, f"{request.symbol}:backtest:{strategy}"),
            strategy_name=strategy_definition.key,
            instrument_id=request.instrument_id,
            start_date=domain_bars[0].timestamp.date(),
            end_date=domain_bars[-1].timestamp.date(),
            initial_capital=capital,
            commission=Decimal("0"),
            slippage_bps=Decimal("1"),
            benchmark_symbol=request.symbol,
        )
        strategy_service = build_strategy_backtest_service(strategy_definition)
        outcome = strategy_service.run(run, domain_bars)
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _backtest_response(
        request.symbol, strategy_definition.key, outcome.result, outcome.latest_decision
    )


@router.get("/strategies", response_model=tuple[StrategyResponse, ...])
def list_strategies() -> tuple[StrategyResponse, ...]:
    """List the selectable strategy variants available to the backtest endpoint."""

    return tuple(
        StrategyResponse(key=item.key, label=item.label, description=item.description)
        for item in STRATEGIES
    )


class StrategyScreenResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_return: Decimal
    max_drawdown: Decimal
    meets_threshold: bool
    next_signal: MasterDecisionResponse | None


class StrategyScreenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    win_rate_threshold: Decimal
    qualifying_count: int
    results: tuple[StrategyScreenResultResponse, ...]


WinRateThreshold = Annotated[Decimal, Query(ge=0, le=1)]


@router.get("/{symbol}/strategy-screen", response_model=StrategyScreenResponse)
def market_data_strategy_screen(
    symbol: SymbolPath,
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    days: BacktestDays = 1825,
    capital: Annotated[Decimal, Query(gt=0)] = Decimal("10000"),
    win_rate_threshold: WinRateThreshold = Decimal("0.8"),
) -> StrategyScreenResponse:
    """Backtest every named strategy variant on one symbol and compare real win rates.

    Each variant runs against the exact same historical bars. Nothing here targets
    or manufactures a win rate — some symbols/windows may have zero strategies
    clearing the threshold, and that is reported honestly via `qualifying_count`.
    """

    request = _history_request(symbol, days)
    domain_bars = _fetch_history(service, request).bars

    try:
        screen = StrategyScreenerService().screen(
            symbol=request.symbol,
            instrument_id=request.instrument_id,
            bars=domain_bars,
            capital=capital,
            win_rate_threshold=win_rate_threshold,
        )
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _screen_response(screen)


def _screen_response(screen: StrategyScreen) -> StrategyScreenResponse:
    return StrategyScreenResponse(
        symbol=screen.symbol,
        win_rate_threshold=screen.win_rate_threshold,
        qualifying_count=screen.qualifying_count,
        results=tuple(
            StrategyScreenResultResponse(
                key=item.key,
                label=item.label,
                description=item.description,
                trade_count=item.trade_count,
                winning_trades=item.winning_trades,
                losing_trades=item.losing_trades,
                win_rate=item.win_rate,
                total_return=item.total_return,
                max_drawdown=item.max_drawdown,
                meets_threshold=item.meets_threshold,
                next_signal=_decision_response(item.next_signal) if item.next_signal else None,
            )
            for item in screen.results
        ),
    )


def _backtest_response(
    symbol: str,
    strategy_key: str,
    result: BacktestResult,
    latest_decision: MasterDecision | None,
) -> BacktestResponse:
    realized = [
        trade.trade.realized_pnl
        for trade in result.trades
        if trade.trade.realized_pnl is not None
    ]
    winning = sum(1 for pnl in realized if pnl > Decimal("0"))
    losing = sum(1 for pnl in realized if pnl < Decimal("0"))
    start_equity = result.equity_curve[0].equity
    end_equity = result.equity_curve[-1].equity
    total_return = (
        end_equity / start_equity - Decimal("1") if start_equity != Decimal("0") else Decimal("0")
    )
    return BacktestResponse(
        symbol=symbol,
        strategy=strategy_key,
        start=result.equity_curve[0].timestamp,
        end=result.equity_curve[-1].timestamp,
        bar_count=len(result.equity_curve),
        initial_capital=result.run.initial_capital,
        final_equity=end_equity,
        metrics=BacktestMetricsResponse(
            success_rate=result.metrics.win_rate,
            total_return=total_return,
            cagr=result.metrics.cagr,
            sharpe=result.metrics.sharpe,
            sortino=result.metrics.sortino,
            calmar=result.metrics.calmar,
            profit_factor=result.metrics.profit_factor,
            max_drawdown=result.metrics.max_drawdown,
            exposure=result.metrics.exposure,
            trade_count=result.metrics.trade_count,
            winning_trades=winning,
            losing_trades=losing,
        ),
        equity_curve=tuple(
            EquityPointResponse(timestamp=point.timestamp, equity=point.equity)
            for point in result.equity_curve
        ),
        trades=tuple(
            TradeRecordResponse(
                entry_at=trade.trade.entry_at,
                entry_price=trade.trade.entry_price.value,
                exit_at=trade.trade.exit_at,
                exit_price=trade.trade.exit_price.value if trade.trade.exit_price else None,
                quantity=trade.trade.quantity.value,
                realized_pnl=trade.trade.realized_pnl,
                entry_reason=trade.entry_reason,
                exit_reason=trade.exit_reason,
            )
            for trade in result.trades
        ),
        next_signal=_decision_response(latest_decision) if latest_decision else None,
    )
