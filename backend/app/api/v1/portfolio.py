"""Portfolio execution endpoint.

Runs the AI master-decision strategy across a universe of symbols with one shared
capital base (default $10,000), then returns the aggregated portfolio: equity,
cash-versus-invested split, blended success rate, every executed trade, the
forward-looking next signal per symbol (upcoming planned trades), and the combined
equity curve. Every sleeve is driven by real provider history; unavailable symbols
are reported in `errors` rather than faked.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import (
    MasterDecisionResponse,
    _decision_response,
    get_market_data_service,
)
from backend.app.application.market_data import MarketDataService
from backend.app.application.portfolio_execution import (
    PortfolioExecution,
    PortfolioExecutionService,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# The Magnificent Seven plus a diversified slice of other high-liquidity names
# (semis, streaming, financials, energy, entertainment, cloud, growth) so the
# portfolio isn't just a tech-concentration bet.
DEFAULT_UNIVERSE = (
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "AMD", "NFLX", "JPM", "XOM", "DIS", "AVGO", "PLTR", "CRM",
)
MAX_RANGE_DAYS = 3660

ExecuteDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]
Capital = Annotated[Decimal, Query(gt=0)]


class SleeveResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    allocated: Decimal
    current_value: Decimal
    realized_pnl: Decimal
    return_pct: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    holding: bool
    last_close: Decimal
    next_signal: MasterDecisionResponse


class PortfolioTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    entry_at: datetime
    entry_price: Decimal
    exit_at: datetime | None
    exit_price: Decimal | None
    quantity: Decimal
    realized_pnl: Decimal | None
    entry_reason: str
    exit_reason: str | None


class PlannedTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    last_close: Decimal
    action: str
    confidence: Decimal
    risk_score: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    expected_r_multiple: Decimal
    explanation: str


class EquityPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    on: str
    equity: Decimal


class SleeveErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    detail: str


class PortfolioExecutionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str
    initial_capital: Decimal
    total_equity: Decimal
    cash: Decimal
    invested: Decimal
    total_pnl: Decimal
    total_return: Decimal
    success_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    max_drawdown: Decimal
    symbol_count: int
    sleeves: tuple[SleeveResponse, ...]
    planned_trades: tuple[PlannedTradeResponse, ...]
    trades: tuple[PortfolioTradeResponse, ...]
    equity_curve: tuple[EquityPointResponse, ...]
    errors: tuple[SleeveErrorResponse, ...]


# Cap the blotter the API serializes; the aggregate metrics still cover every trade.
TRADE_LIMIT = 500


@router.get("/execute", response_model=PortfolioExecutionResponse)
def execute_portfolio(
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    symbols: Annotated[list[str] | None, Query()] = None,
    capital: Capital = Decimal("10000"),
    days: ExecuteDays = 1825,
) -> PortfolioExecutionResponse:
    """Execute the AI strategy across the universe and aggregate the portfolio."""

    universe = symbols if symbols else list(DEFAULT_UNIVERSE)
    execution = PortfolioExecutionService(market_data=service).run(
        symbols=universe, capital=capital, days=days
    )
    return _execution_response(execution)


def _execution_response(execution: PortfolioExecution) -> PortfolioExecutionResponse:
    sleeves = tuple(
        SleeveResponse(
            symbol=sleeve.symbol,
            allocated=sleeve.allocated,
            current_value=sleeve.current_value,
            realized_pnl=sleeve.realized_pnl,
            return_pct=(
                sleeve.current_value / sleeve.allocated - Decimal("1")
                if sleeve.allocated > Decimal("0")
                else Decimal("0")
            ),
            trade_count=sleeve.trade_count,
            winning_trades=sleeve.winning_trades,
            losing_trades=sleeve.losing_trades,
            win_rate=sleeve.win_rate,
            holding=sleeve.holding,
            last_close=sleeve.last_close,
            next_signal=_decision_response(sleeve.next_signal),
        )
        for sleeve in execution.sleeves
    )
    planned = tuple(
        PlannedTradeResponse(
            symbol=sleeve.symbol,
            last_close=sleeve.last_close,
            action=sleeve.next_signal.action.value,
            confidence=sleeve.next_signal.confidence.value,
            risk_score=sleeve.next_signal.risk_score.value,
            stop_loss=sleeve.next_signal.stop_loss.value if sleeve.next_signal.stop_loss else None,
            take_profit=(
                sleeve.next_signal.take_profit.value if sleeve.next_signal.take_profit else None
            ),
            expected_r_multiple=sleeve.next_signal.expected_r_multiple,
            explanation=sleeve.next_signal.explanation,
        )
        for sleeve in execution.sleeves
        if sleeve.next_signal.action.value != "hold"
    )
    trades = tuple(
        PortfolioTradeResponse(
            symbol=item.symbol,
            entry_at=item.trade.entry_at,
            entry_price=item.trade.entry_price.value,
            exit_at=item.trade.exit_at,
            exit_price=item.trade.exit_price.value if item.trade.exit_price else None,
            quantity=item.trade.quantity.value,
            realized_pnl=item.trade.realized_pnl,
            entry_reason=item.entry_reason,
            exit_reason=item.exit_reason,
        )
        for item in execution.trades[-TRADE_LIMIT:]
    )
    return PortfolioExecutionResponse(
        generated_at=datetime.now().astimezone().isoformat(),
        initial_capital=execution.initial_capital,
        total_equity=execution.total_equity,
        cash=execution.cash,
        invested=execution.invested,
        total_pnl=execution.total_pnl,
        total_return=execution.total_return,
        success_rate=execution.success_rate,
        trade_count=execution.trade_count,
        winning_trades=execution.winning_trades,
        losing_trades=execution.losing_trades,
        max_drawdown=execution.max_drawdown,
        symbol_count=len(execution.sleeves),
        sleeves=sleeves,
        planned_trades=planned,
        trades=trades,
        equity_curve=tuple(
            EquityPointResponse(on=point.on.isoformat(), equity=point.equity)
            for point in execution.equity_curve
        ),
        errors=tuple(
            SleeveErrorResponse(symbol=error.symbol, detail=error.detail)
            for error in execution.errors
        ),
    )
