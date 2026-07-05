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

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import (
    MasterDecisionResponse,
    _decision_response,
    get_market_data_service,
)
from backend.app.api.v1.options import PRICING_NOTE, get_options_provider
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import OptionsStyle
from backend.app.application.options_forward_ledger import (
    LedgerSnapshot,
    OptionsForwardLedgerService,
)
from backend.app.application.options_portfolio_execution import (
    OptionsPortfolioExecution,
    OptionsPortfolioExecutionService,
)
from backend.app.domain.options import OptionsProvider

router = APIRouter(prefix="/options-portfolio", tags=["options-portfolio"])

# True same-day (0DTE) expiries are only reliably listed on broad index ETFs;
# single-name equities generally only list weekly (Friday) expiries. This
# universe blends both so the 0DTE style has real-world grounding and the
# weekly style covers a wider, still highly-optioned slice of single names.
DEFAULT_UNIVERSE = (
    "SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "GOOGL",
)
MAX_RANGE_DAYS = 3660
LEDGER_CAPITAL = Decimal("10000")

ExecuteDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]
Capital = Annotated[Decimal, Query(gt=0)]

LEDGER_NOTE = (
    "Live paper ledger: positions are opened and marked at real quoted prices "
    "from the live options chain (no Black-Scholes modeling). The track record "
    "only grows forward from whenever this was first run and resets if the "
    "backend process restarts — it is not yet backed by durable storage."
)


def get_options_ledger(
    request: Request,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    options: Annotated[OptionsProvider, Depends(get_options_provider)],
) -> OptionsForwardLedgerService:
    """Provide the process-lifetime options paper ledger (in-memory singleton).

    Mirrors how the existing stock PaperBroker holds state in memory rather
    than a database; see the module docstring on OptionsForwardLedgerService.
    """

    state = request.app.state
    ledger = getattr(state, "options_ledger", None)
    if ledger is None:
        ledger = OptionsForwardLedgerService(options=options, market_data=market_data)
        per_symbol = (LEDGER_CAPITAL / Decimal(len(DEFAULT_UNIVERSE))).quantize(Decimal("0.01"))
        for symbol in DEFAULT_UNIVERSE:
            ledger.ensure_symbol(symbol, per_symbol)
        state.options_ledger = ledger
    return ledger


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


class LedgerOpenPositionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    style: str
    option_side: str
    contract_symbol: str
    strike: Decimal
    expiration: str
    opened_at: str
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    entry_reason: str
    mark_premium: Decimal | None
    unrealized_pnl: Decimal | None


class LedgerClosedPositionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    style: str
    option_side: str
    contract_symbol: str
    strike: Decimal
    expiration: str
    opened_at: str
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    entry_reason: str
    closed_at: str
    exit_underlying: Decimal
    exit_premium: Decimal
    realized_pnl: Decimal
    settlement: str


class LedgerSnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str
    real_quotes: bool
    note: str
    cash_by_symbol: dict[str, Decimal]
    realized_pnl_total: Decimal
    open_positions: tuple[LedgerOpenPositionResponse, ...]
    closed_positions: tuple[LedgerClosedPositionResponse, ...]


def _snapshot_response(snapshot: LedgerSnapshot) -> LedgerSnapshotResponse:
    realized_total = sum(
        (position.realized_pnl for position in snapshot.closed_positions), Decimal("0")
    )
    return LedgerSnapshotResponse(
        generated_at=datetime.now().astimezone().isoformat(),
        real_quotes=True,
        note=LEDGER_NOTE,
        cash_by_symbol=snapshot.cash_by_symbol,
        realized_pnl_total=realized_total,
        open_positions=tuple(
            LedgerOpenPositionResponse(
                symbol=marked.position.symbol,
                style=marked.position.style.value,
                option_side=marked.position.option_side.value,
                contract_symbol=marked.position.contract_symbol,
                strike=marked.position.strike,
                expiration=marked.position.expiration.isoformat(),
                opened_at=marked.position.opened_at.isoformat(),
                entry_underlying=marked.position.entry_underlying,
                entry_premium=marked.position.entry_premium,
                contracts=marked.position.contracts,
                entry_reason=marked.position.entry_reason,
                mark_premium=marked.mark_premium,
                unrealized_pnl=marked.unrealized_pnl,
            )
            for marked in snapshot.open_positions
        ),
        closed_positions=tuple(
            LedgerClosedPositionResponse(
                symbol=position.symbol,
                style=position.style.value,
                option_side=position.option_side.value,
                contract_symbol=position.contract_symbol,
                strike=position.strike,
                expiration=position.expiration.isoformat(),
                opened_at=position.opened_at.isoformat(),
                entry_underlying=position.entry_underlying,
                entry_premium=position.entry_premium,
                contracts=position.contracts,
                entry_reason=position.entry_reason,
                closed_at=position.closed_at.isoformat(),
                exit_underlying=position.exit_underlying,
                exit_premium=position.exit_premium,
                realized_pnl=position.realized_pnl,
                settlement=position.settlement,
            )
            for position in snapshot.closed_positions
        ),
    )


@router.get("/paper-ledger", response_model=LedgerSnapshotResponse)
def get_paper_ledger(
    ledger: Annotated[OptionsForwardLedgerService, Depends(get_options_ledger)],
) -> LedgerSnapshotResponse:
    """Read-only snapshot of the live paper ledger — no side effects."""

    return _snapshot_response(ledger.snapshot())


@router.post("/paper-ledger/tick", response_model=LedgerSnapshotResponse)
def tick_paper_ledger(
    ledger: Annotated[OptionsForwardLedgerService, Depends(get_options_ledger)],
    style: OptionsStyle = OptionsStyle.WEEKLY,
    max_dte: int = 8,
) -> LedgerSnapshotResponse:
    """Settle matured/delisted positions, then open new ones from live signals.

    Intended to be called periodically (e.g. once per trading day). Each
    symbol in the ledger's universe opens at most one position per style at a
    time — a symbol already holding a position is left alone until it closes.
    """

    ledger.tick()
    for symbol in DEFAULT_UNIVERSE:
        try:
            ledger.open_if_signal(symbol, style, max_dte)
        except Exception:  # noqa: BLE001 - one bad symbol must not sink the tick
            continue
    return _snapshot_response(ledger.snapshot())
