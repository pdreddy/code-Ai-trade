"""Modeled options-portfolio execution endpoint.

Runs the Black-Scholes-modeled 0DTE/weekly options strategy across a dedicated
universe with its own capital base (default $10,000, separate from the equity
portfolio), then aggregates the sleeves into one options portfolio: equity
curve, blended success rate, every trade, and each symbol's forward-looking
next signal. See ``options_backtesting.py`` for why premiums are modeled
rather than real quoted prices.
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
from backend.app.api.v1.options import PRICING_NOTE
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import OptionsStyle
from backend.app.application.options_portfolio_execution import (
    OptionsPortfolioExecution,
    OptionsPortfolioExecutionService,
)

router = APIRouter(prefix="/options-portfolio", tags=["options-portfolio"])

# True same-day (0DTE) expiries are only reliably listed on broad index ETFs;
# single-name equities generally only list weekly (Friday) expiries. This
# universe blends both so the 0DTE style has real-world grounding and the
# weekly style still covers the platform's Magnificent 7 names.
DEFAULT_UNIVERSE = ("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA")
MAX_RANGE_DAYS = 3660

ExecuteDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]
Capital = Annotated[Decimal, Query(gt=0)]


class OptionsSleeveResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    allocated: Decimal
    final_equity: Decimal
    return_pct: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    next_signal: MasterDecisionResponse | None


class OptionsPortfolioTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    option_side: str
    strike: Decimal
    expiration: str
    entry_at: str
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    exit_at: str
    exit_underlying: Decimal
    exit_premium: Decimal
    realized_pnl: Decimal
    entry_reason: str
    exit_reason: str


class OptionsPortfolioEquityPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    on: str
    equity: Decimal


class OptionsSleeveErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    detail: str


class OptionsPortfolioExecutionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str
    style: str
    modeled: bool
    pricing_note: str
    initial_capital: Decimal
    total_equity: Decimal
    total_pnl: Decimal
    total_return: Decimal
    success_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    max_drawdown: Decimal
    symbol_count: int
    sleeves: tuple[OptionsSleeveResponse, ...]
    trades: tuple[OptionsPortfolioTradeResponse, ...]
    equity_curve: tuple[OptionsPortfolioEquityPointResponse, ...]
    errors: tuple[OptionsSleeveErrorResponse, ...]


# Cap the blotter the API serializes; the aggregate metrics still cover every trade.
TRADE_LIMIT = 500


@router.get("/execute", response_model=OptionsPortfolioExecutionResponse)
def execute_options_portfolio(
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    symbols: Annotated[list[str] | None, Query()] = None,
    style: OptionsStyle = OptionsStyle.WEEKLY,
    capital: Capital = Decimal("10000"),
    days: ExecuteDays = 1825,
) -> OptionsPortfolioExecutionResponse:
    """Execute the modeled options strategy across the universe and aggregate it."""

    universe = symbols if symbols else list(DEFAULT_UNIVERSE)
    execution = OptionsPortfolioExecutionService(market_data=service).run(
        symbols=universe, capital=capital, days=days, style=style
    )
    return _execution_response(execution)


def _execution_response(
    execution: OptionsPortfolioExecution,
) -> OptionsPortfolioExecutionResponse:
    sleeves = tuple(
        OptionsSleeveResponse(
            symbol=sleeve.symbol,
            allocated=sleeve.allocated,
            final_equity=sleeve.final_equity,
            return_pct=(
                sleeve.final_equity / sleeve.allocated - Decimal("1")
                if sleeve.allocated > Decimal("0")
                else Decimal("0")
            ),
            trade_count=sleeve.trade_count,
            winning_trades=sleeve.winning_trades,
            losing_trades=sleeve.losing_trades,
            win_rate=sleeve.win_rate,
            next_signal=_decision_response(sleeve.next_signal) if sleeve.next_signal else None,
        )
        for sleeve in execution.sleeves
    )
    trades = tuple(
        OptionsPortfolioTradeResponse(
            symbol=item.symbol,
            option_side=item.trade.option_side.value,
            strike=item.trade.strike,
            expiration=item.trade.expiration.isoformat(),
            entry_at=item.trade.entry_at.isoformat(),
            entry_underlying=item.trade.entry_underlying,
            entry_premium=item.trade.entry_premium,
            contracts=item.trade.contracts,
            exit_at=item.trade.exit_at.isoformat(),
            exit_underlying=item.trade.exit_underlying,
            exit_premium=item.trade.exit_premium,
            realized_pnl=item.trade.realized_pnl,
            entry_reason=item.trade.entry_reason,
            exit_reason=item.trade.exit_reason,
        )
        for item in execution.trades[-TRADE_LIMIT:]
    )
    return OptionsPortfolioExecutionResponse(
        generated_at=datetime.now().astimezone().isoformat(),
        style=execution.style.value,
        modeled=True,
        pricing_note=PRICING_NOTE,
        initial_capital=execution.initial_capital,
        total_equity=execution.total_equity,
        total_pnl=execution.total_pnl,
        total_return=execution.total_return,
        success_rate=execution.success_rate,
        trade_count=execution.trade_count,
        winning_trades=execution.winning_trades,
        losing_trades=execution.losing_trades,
        max_drawdown=execution.max_drawdown,
        symbol_count=len(execution.sleeves),
        sleeves=sleeves,
        trades=trades,
        equity_curve=tuple(
            OptionsPortfolioEquityPointResponse(on=point.on.isoformat(), equity=point.equity)
            for point in execution.equity_curve
        ),
        errors=tuple(
            OptionsSleeveErrorResponse(symbol=error.symbol, detail=error.detail)
            for error in execution.errors
        ),
    )
