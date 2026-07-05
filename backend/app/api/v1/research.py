"""Research report endpoints for paper-trading candidates and historical results."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.application.daily_research import (
    DEFAULT_RESEARCH_SYMBOLS,
    AgentScore,
    BacktestSummary,
    BenchmarkComparison,
    DailyResearchService,
    DailyTrade,
    EquityPoint,
    HoldingSnapshot,
    NextDayCandidate,
    OptionsWatchCandidate,
    PortfolioSummary,
    ZeroDteOptionIntent,
)

router = APIRouter(prefix="/research", tags=["research"])
CAPITAL_QUERY = Query(default=Decimal("10000"), gt=0)


class EquityPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: date
    equity: Decimal
    drawdown: Decimal
    daily_pnl: Decimal
    daily_return: Decimal


class BenchmarkComparisonResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark: str
    benchmark_return: Decimal
    strategy_return: Decimal
    outperformance: Decimal
    benchmark_drawdown: Decimal
    risk_label: str


class AgentScoreResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    score: Decimal
    confidence: Decimal
    reason: str


class HoldingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    position: str
    shares: Decimal
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    today_change: Decimal
    weight: Decimal
    risk_score: Decimal
    ai_score: Decimal
    confidence: Decimal
    sector: str
    industry: str
    stop_loss: Decimal | None
    take_profit: Decimal | None
    holding_days: int
    status: str


class TradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    entry_date: date
    entry_price: Decimal
    exit_date: date | None
    exit_price: Decimal | None
    quantity: Decimal
    pnl: Decimal | None
    return_pct: Decimal | None
    reason: str
    trade_id: str
    direction: str
    holding_period_days: int
    position_size: Decimal
    entry_signal: str
    exit_signal: str
    strategy_name: str
    regime: str
    ai_confidence: Decimal
    risk_reward: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    commission: Decimal
    slippage: Decimal
    screenshot_placeholder: str
    notes: str


class BacktestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    start_date: date
    end_date: date
    bars: int
    total_return: Decimal
    win_rate: Decimal
    max_drawdown: Decimal
    trade_count: int
    open_position: bool
    starting_capital: Decimal
    ending_equity: Decimal
    trades: tuple[TradeResponse, ...]
    equity_curve: tuple[EquityPointResponse, ...]
    benchmark_comparisons: tuple[BenchmarkComparisonResponse, ...]
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    profit_factor: Decimal
    expectancy: Decimal
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    consecutive_wins: int
    consecutive_losses: int
    recovery_time_days: int
    exposure: Decimal
    volatility: Decimal
    alpha: Decimal
    beta: Decimal
    information_ratio: Decimal
    tracking_error: Decimal
    treynor_ratio: Decimal
    omega_ratio: Decimal
    skew: Decimal
    kurtosis: Decimal
    mar_ratio: Decimal


class CandidateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    signal_date: date
    action: str
    confidence: Decimal
    planned_execution: str
    last_close: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    suggested_quantity: Decimal
    suggested_notional: Decimal
    reasons: tuple[str, ...]
    ai_score: Decimal
    strategy: str
    risk_reward: Decimal
    expected_return: Decimal
    expected_holding_days: int
    catalysts: tuple[str, ...]
    news_summary: str
    institutional_flow: str
    agent_scores: tuple[AgentScoreResponse, ...]
    final_score: Decimal
    risk_score: Decimal


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    starting_capital: Decimal
    ending_equity: Decimal
    total_return: Decimal
    open_positions: int
    closed_trades: int
    win_rate: Decimal
    max_drawdown: Decimal
    cash_policy: str
    cash: Decimal
    invested: Decimal
    today_pnl: Decimal
    annualized_return: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    expectancy: Decimal
    average_winner: Decimal
    average_loser: Decimal
    risk_score: Decimal
    holdings: tuple[HoldingResponse, ...]
    equity_curve: tuple[EquityPointResponse, ...]


class OptionsWatchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    signal_date: date
    underlying_action: str
    watch_type: str
    urgency: Decimal
    underlying_last_close: Decimal
    suggested_underlying_notional: Decimal
    rationale: tuple[str, ...]


class ZeroDteOptionIntentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    signal_date: date
    option_type: str
    direction: str
    expiration: date
    underlying_price: Decimal
    strike: Decimal
    max_premium_budget: Decimal
    status: str
    rationale: tuple[str, ...]


class DailyResearchReportResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    candidates: tuple[CandidateResponse, ...]
    backtests: tuple[BacktestResponse, ...]
    portfolio: PortfolioResponse
    options_watchlist: tuple[OptionsWatchResponse, ...]
    zero_dte_option_intents: tuple[ZeroDteOptionIntentResponse, ...]


@router.get("/daily-report", response_model=DailyResearchReportResponse)
def daily_report(
    symbols: tuple[str, ...] = Query(default=DEFAULT_RESEARCH_SYMBOLS, min_length=1, max_length=12),
    capital: Decimal = CAPITAL_QUERY,
) -> DailyResearchReportResponse:
    """Return real historical strategy results and next-session paper candidates."""

    try:
        report = DailyResearchService().build_report(symbols, starting_capital=capital)
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Real research provider access failed; no synthetic trades were generated.",
        ) from exc
    return DailyResearchReportResponse(
        generated_at=report.generated_at,
        candidates=tuple(_candidate(candidate) for candidate in report.candidates),
        backtests=tuple(_backtest(backtest) for backtest in report.backtests),
        portfolio=_portfolio(report.portfolio),
        options_watchlist=tuple(_options_watch(item) for item in report.options_watchlist),
        zero_dte_option_intents=tuple(
            _zero_dte_option_intent(item) for item in report.zero_dte_option_intents
        ),
    )


def _candidate(candidate: NextDayCandidate) -> CandidateResponse:
    return CandidateResponse(
        symbol=candidate.symbol,
        signal_date=candidate.signal_date,
        action=candidate.action,
        confidence=_round(candidate.confidence),
        planned_execution=candidate.planned_execution,
        last_close=_round(candidate.last_close),
        stop_loss=_round(candidate.stop_loss) if candidate.stop_loss is not None else None,
        take_profit=_round(candidate.take_profit) if candidate.take_profit is not None else None,
        suggested_quantity=_round(candidate.suggested_quantity),
        suggested_notional=_round(candidate.suggested_notional),
        reasons=candidate.reasons,
        ai_score=_round(candidate.ai_score),
        strategy=candidate.strategy,
        risk_reward=_round(candidate.risk_reward),
        expected_return=_round(candidate.expected_return),
        expected_holding_days=candidate.expected_holding_days,
        catalysts=candidate.catalysts,
        news_summary=candidate.news_summary,
        institutional_flow=candidate.institutional_flow,
        agent_scores=tuple(_agent_score(agent) for agent in candidate.agent_scores),
        final_score=_round(candidate.final_score),
        risk_score=_round(candidate.risk_score),
    )


def _backtest(backtest: BacktestSummary) -> BacktestResponse:
    return BacktestResponse(
        symbol=backtest.symbol,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
        bars=backtest.bars,
        total_return=_round(backtest.total_return),
        win_rate=_round(backtest.win_rate),
        max_drawdown=_round(backtest.max_drawdown),
        trade_count=backtest.trade_count,
        open_position=backtest.open_position,
        starting_capital=_round(backtest.starting_capital),
        ending_equity=_round(backtest.ending_equity),
        trades=tuple(_trade(trade) for trade in backtest.trades),
        equity_curve=tuple(_equity_point(point) for point in backtest.equity_curve),
        benchmark_comparisons=tuple(
            _benchmark_comparison(item) for item in backtest.benchmark_comparisons
        ),
        sharpe_ratio=_round(backtest.sharpe_ratio),
        sortino_ratio=_round(backtest.sortino_ratio),
        calmar_ratio=_round(backtest.calmar_ratio),
        profit_factor=_round(backtest.profit_factor),
        expectancy=_round(backtest.expectancy),
        average_win=_round(backtest.average_win),
        average_loss=_round(backtest.average_loss),
        largest_win=_round(backtest.largest_win),
        largest_loss=_round(backtest.largest_loss),
        consecutive_wins=backtest.consecutive_wins,
        consecutive_losses=backtest.consecutive_losses,
        recovery_time_days=backtest.recovery_time_days,
        exposure=_round(backtest.exposure),
        volatility=_round(backtest.volatility),
        alpha=_round(backtest.alpha),
        beta=_round(backtest.beta),
        information_ratio=_round(backtest.information_ratio),
        tracking_error=_round(backtest.tracking_error),
        treynor_ratio=_round(backtest.treynor_ratio),
        omega_ratio=_round(backtest.omega_ratio),
        skew=_round(backtest.skew),
        kurtosis=_round(backtest.kurtosis),
        mar_ratio=_round(backtest.mar_ratio),
    )


def _trade(trade: DailyTrade) -> TradeResponse:
    return TradeResponse(
        symbol=trade.symbol,
        entry_date=trade.entry_date,
        entry_price=_round(trade.entry_price),
        exit_date=trade.exit_date,
        exit_price=_round(trade.exit_price) if trade.exit_price is not None else None,
        quantity=_round(trade.quantity),
        pnl=_round(trade.pnl) if trade.pnl is not None else None,
        return_pct=_round(trade.return_pct) if trade.return_pct is not None else None,
        reason=trade.reason,
        trade_id=trade.trade_id,
        direction=trade.direction,
        holding_period_days=trade.holding_period_days,
        position_size=_round(trade.position_size),
        entry_signal=trade.entry_signal,
        exit_signal=trade.exit_signal,
        strategy_name=trade.strategy_name,
        regime=trade.regime,
        ai_confidence=_round(trade.ai_confidence),
        risk_reward=_round(trade.risk_reward),
        stop_loss=_round(trade.stop_loss) if trade.stop_loss is not None else None,
        take_profit=_round(trade.take_profit) if trade.take_profit is not None else None,
        gross_pnl=_round(trade.gross_pnl) if trade.gross_pnl is not None else None,
        net_pnl=_round(trade.net_pnl) if trade.net_pnl is not None else None,
        commission=_round(trade.commission),
        slippage=_round(trade.slippage),
        screenshot_placeholder="not_captured",
        notes=trade.notes,
    )


def _portfolio(portfolio: PortfolioSummary) -> PortfolioResponse:
    return PortfolioResponse(
        starting_capital=_round(portfolio.starting_capital),
        ending_equity=_round(portfolio.ending_equity),
        total_return=_round(portfolio.total_return),
        open_positions=portfolio.open_positions,
        closed_trades=portfolio.closed_trades,
        win_rate=_round(portfolio.win_rate),
        max_drawdown=_round(portfolio.max_drawdown),
        cash_policy=portfolio.cash_policy,
        cash=_round(portfolio.cash),
        invested=_round(portfolio.invested),
        today_pnl=_round(portfolio.today_pnl),
        annualized_return=_round(portfolio.annualized_return),
        profit_factor=_round(portfolio.profit_factor),
        sharpe_ratio=_round(portfolio.sharpe_ratio),
        sortino_ratio=_round(portfolio.sortino_ratio),
        calmar_ratio=_round(portfolio.calmar_ratio),
        expectancy=_round(portfolio.expectancy),
        average_winner=_round(portfolio.average_winner),
        average_loser=_round(portfolio.average_loser),
        risk_score=_round(portfolio.risk_score),
        holdings=tuple(_holding(holding) for holding in portfolio.holdings),
        equity_curve=tuple(_equity_point(point) for point in portfolio.equity_curve),
    )


def _options_watch(candidate: OptionsWatchCandidate) -> OptionsWatchResponse:
    return OptionsWatchResponse(
        symbol=candidate.symbol,
        signal_date=candidate.signal_date,
        underlying_action=candidate.underlying_action,
        watch_type=candidate.watch_type,
        urgency=_round(candidate.urgency),
        underlying_last_close=_round(candidate.underlying_last_close),
        suggested_underlying_notional=_round(candidate.suggested_underlying_notional),
        rationale=candidate.rationale,
    )


def _zero_dte_option_intent(intent: ZeroDteOptionIntent) -> ZeroDteOptionIntentResponse:
    return ZeroDteOptionIntentResponse(
        symbol=intent.symbol,
        signal_date=intent.signal_date,
        option_type=intent.option_type,
        direction=intent.direction,
        expiration=intent.expiration,
        underlying_price=_round(intent.underlying_price),
        strike=_round(intent.strike),
        max_premium_budget=_round(intent.max_premium_budget),
        status=intent.status,
        rationale=intent.rationale,
    )


def _equity_point(point: EquityPoint) -> EquityPointResponse:
    return EquityPointResponse(
        session=point.session,
        equity=_round(point.equity),
        drawdown=_round(point.drawdown),
        daily_pnl=_round(point.daily_pnl),
        daily_return=_round(point.daily_return),
    )


def _benchmark_comparison(item: BenchmarkComparison) -> BenchmarkComparisonResponse:
    return BenchmarkComparisonResponse(
        benchmark=item.benchmark,
        benchmark_return=_round(item.benchmark_return),
        strategy_return=_round(item.strategy_return),
        outperformance=_round(item.outperformance),
        benchmark_drawdown=_round(item.benchmark_drawdown),
        risk_label=item.risk_label,
    )


def _agent_score(agent: AgentScore) -> AgentScoreResponse:
    return AgentScoreResponse(
        name=agent.name,
        score=_round(agent.score),
        confidence=_round(agent.confidence),
        reason=agent.reason,
    )


def _holding(holding: HoldingSnapshot) -> HoldingResponse:
    return HoldingResponse(
        symbol=holding.symbol,
        position=holding.position,
        shares=_round(holding.shares),
        average_cost=_round(holding.average_cost),
        current_price=_round(holding.current_price),
        market_value=_round(holding.market_value),
        unrealized_pnl=_round(holding.unrealized_pnl),
        realized_pnl=_round(holding.realized_pnl),
        today_change=_round(holding.today_change),
        weight=_round(holding.weight),
        risk_score=_round(holding.risk_score),
        ai_score=_round(holding.ai_score),
        confidence=_round(holding.confidence),
        sector=holding.sector,
        industry=holding.industry,
        stop_loss=_round(holding.stop_loss) if holding.stop_loss is not None else None,
        take_profit=_round(holding.take_profit) if holding.take_profit is not None else None,
        holding_days=holding.holding_days,
        status=holding.status,
    )


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
