"""Research report endpoints for paper-trading candidates and historical results."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.application.daily_research import (
    DEFAULT_RESEARCH_SYMBOLS,
    BacktestSummary,
    DailyResearchService,
    DailyTrade,
    NextDayCandidate,
    OptionsWatchCandidate,
    PortfolioSummary,
)

router = APIRouter(prefix="/research", tags=["research"])
CAPITAL_QUERY = Query(default=Decimal("10000"), gt=0)


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


class DailyResearchReportResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    candidates: tuple[CandidateResponse, ...]
    backtests: tuple[BacktestResponse, ...]
    portfolio: PortfolioResponse
    options_watchlist: tuple[OptionsWatchResponse, ...]


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
    )


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


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
