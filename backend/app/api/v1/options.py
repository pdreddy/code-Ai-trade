"""Options research endpoint focused on 0DTE and weekly trading.

Returns near-term (0DTE / weekly) contracts, ranked unusual options activity, and
AI-aligned upcoming planned option trades for a symbol. The chain is real Yahoo
data; the direction of the planned trades comes from the same master decision that
drives the rest of the platform.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import (
    MasterDecisionResponse,
    _decision_response,
    get_market_data_service,
)
from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import MasterDecisionEngine
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import (
    OptionsBacktester,
    OptionsBacktestResult,
    OptionsStyle,
    OptionsTrade,
)
from backend.app.application.options_research import (
    DEFAULT_MAX_DTE,
    OptionsResearch,
    OptionsResearchService,
    PlannedOptionTrade,
)
from backend.app.application.options_strategy_playbook import (
    OPTIONS_STRATEGY_PLAYBOOK,
    OptionsStrategyPlaybookItem,
)
from backend.app.application.options_strategy_screen import (
    DEFAULT_MIN_WIN_RATE,
    OptionsStrategyScreen,
    OptionsStrategyScreenService,
)
from backend.app.application.portfolio_execution import instrument_id
from backend.app.core.config import Settings, get_settings
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.options import OptionContract, OptionsProvider
from backend.app.domain.providers import HistoricalMarketDataRequest
from backend.app.infrastructure.providers.factory import create_options_provider
from backend.app.infrastructure.providers.tradier_options import TradierProviderError
from backend.app.infrastructure.providers.yahoo import YahooFinanceProviderError

router = APIRouter(prefix="/options", tags=["options"])

SymbolPath = Annotated[str, Path(min_length=1, max_length=12)]
MaxDte = Annotated[int, Query(ge=0, le=45)]
MAX_RANGE_DAYS = 3660
BacktestDays = Annotated[int, Query(ge=210, le=MAX_RANGE_DAYS)]
BacktestCapital = Annotated[Decimal, Query(gt=0)]
MinWinRate = Annotated[Decimal, Query(ge=0, le=1)]

# Both providers surface upstream failures as one of these; caught together
# wherever an options fetch can fail regardless of which is configured.
OptionsProviderErrors = (YahooFinanceProviderError, TradierProviderError)


def get_options_provider(settings: Annotated[Settings, Depends(get_settings)]) -> OptionsProvider:
    """Provide the configured options provider (overridable in tests)."""

    return create_options_provider(settings)


class OptionsStrategyPlaybookResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    objective: str
    setup: tuple[str, ...]
    required_data: tuple[str, ...]
    risk_rules: tuple[str, ...]
    preferred_symbols: tuple[str, ...]
    scanner_ready: bool


class OptionContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_symbol: str
    option_type: str
    strike: Decimal
    expiration: date
    days_to_expiry: int
    last_price: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    volume: int
    open_interest: int
    implied_volatility: Decimal | None
    in_the_money: bool
    volume_oi_ratio: Decimal


class UnusualContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract: OptionContractResponse
    volume_oi_ratio: Decimal


class PlannedOptionTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract: OptionContractResponse
    option_side: str
    entry_price: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    stop_loss_underlying: Decimal | None
    take_profit_underlying: Decimal | None
    target_return: Decimal | None
    max_loss: Decimal | None
    trade_timing: str
    rationale: str


class OptionsResearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    underlying_price: Decimal
    as_of: str
    max_dte: int
    near_term_count: int
    zero_dte_count: int
    signal: MasterDecisionResponse
    unusual_activity: tuple[UnusualContractResponse, ...]
    planned_trades: tuple[PlannedOptionTradeResponse, ...]
    today_planned_trades: tuple[PlannedOptionTradeResponse, ...]
    future_planned_trades: tuple[PlannedOptionTradeResponse, ...]


@router.get("/strategies", response_model=tuple[OptionsStrategyPlaybookResponse, ...])
def options_strategy_playbook() -> tuple[OptionsStrategyPlaybookResponse, ...]:
    """Return deterministic options strategies to implement before AI ranking."""

    return tuple(_playbook_response(item) for item in OPTIONS_STRATEGY_PLAYBOOK)


def _playbook_response(item: OptionsStrategyPlaybookItem) -> OptionsStrategyPlaybookResponse:
    return OptionsStrategyPlaybookResponse(
        key=item.key.value,
        label=item.label,
        objective=item.objective,
        setup=item.setup,
        required_data=item.required_data,
        risk_rules=item.risk_rules,
        preferred_symbols=item.preferred_symbols,
        scanner_ready=item.scanner_ready,
    )


@router.get("/{symbol}", response_model=OptionsResearchResponse)
def options_research(
    symbol: SymbolPath,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    options: Annotated[OptionsProvider, Depends(get_options_provider)],
    max_dte: MaxDte = DEFAULT_MAX_DTE,
) -> OptionsResearchResponse:
    """Return near-term options, unusual activity, and AI-aligned planned trades."""

    service = OptionsResearchService(options=options, market_data=market_data)
    try:
        research = service.research(symbol, max_dte=max_dte)
    except OptionsProviderErrors as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _research_response(research, max_dte)


def _contract_response(contract: OptionContract) -> OptionContractResponse:
    return OptionContractResponse(
        contract_symbol=contract.contract_symbol,
        option_type=contract.option_type.value,
        strike=contract.strike,
        expiration=contract.expiration,
        days_to_expiry=contract.days_to_expiry,
        last_price=contract.last_price,
        bid=contract.bid,
        ask=contract.ask,
        volume=contract.volume,
        open_interest=contract.open_interest,
        implied_volatility=contract.implied_volatility,
        in_the_money=contract.in_the_money,
        volume_oi_ratio=contract.volume_open_interest_ratio,
    )


def _planned_trade_response(item: PlannedOptionTrade) -> PlannedOptionTradeResponse:
    return PlannedOptionTradeResponse(
        contract=_contract_response(item.contract),
        option_side=item.contract.option_type.value,
        entry_price=item.entry_price,
        bid=item.contract.bid,
        ask=item.contract.ask,
        stop_loss_underlying=item.stop_loss_underlying,
        take_profit_underlying=item.take_profit_underlying,
        target_return=item.target_return,
        max_loss=item.max_loss,
        trade_timing="today" if item.contract.days_to_expiry == 0 else "future",
        rationale=item.rationale,
    )


class OptionsTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_side: str
    strike: Decimal
    expiration: date
    entry_at: date
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    exit_at: date
    exit_underlying: Decimal
    exit_premium: Decimal
    realized_pnl: Decimal
    entry_reason: str
    exit_reason: str


class OptionsEquityPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    on: date
    equity: Decimal


class OptionsBacktestMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    win_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    total_return: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal


class OptionsStrategyScoreResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    style: str
    recommended: bool
    meets_threshold: bool
    final_equity: Decimal
    win_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    total_return: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal


class OptionsStrategyScreenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    modeled: bool
    pricing_note: str
    min_win_rate: Decimal
    recommended_style: str | None
    results: tuple[OptionsStrategyScoreResponse, ...]


class OptionsBacktestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    style: str
    modeled: bool
    pricing_note: str
    initial_capital: Decimal
    final_equity: Decimal
    metrics: OptionsBacktestMetricsResponse
    equity_curve: tuple[OptionsEquityPointResponse, ...]
    trades: tuple[OptionsTradeResponse, ...]
    next_signal: MasterDecisionResponse | None


PRICING_NOTE = (
    "Modeled backtest: option premiums are priced theoretically with Black-Scholes "
    "off real historical underlying closes (realized volatility as the IV proxy), "
    "since no historical options-quote data source is available. Underlying "
    "prices, strikes, and expiration mechanics are real; the premium is not a "
    "quoted market price. See the live options chain above for real quotes."
)


@router.get("/{symbol}/strategy-screen", response_model=OptionsStrategyScreenResponse)
def options_strategy_screen(
    symbol: SymbolPath,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    days: BacktestDays = 1825,
    capital: BacktestCapital = Decimal("10000"),
    min_win_rate: MinWinRate = DEFAULT_MIN_WIN_RATE,
) -> OptionsStrategyScreenResponse:
    """Rank 0DTE versus weekly modeled options strategies by winning metrics."""

    today = datetime.now(UTC).date()
    request = HistoricalMarketDataRequest(
        instrument_id=instrument_id(symbol),
        symbol=symbol.upper(),
        start=today - timedelta(days=days),
        end=today + timedelta(days=1),
    )
    try:
        bars = market_data.fetch_daily_history(request).bars
        screen = OptionsStrategyScreenService().screen(
            request.instrument_id,
            request.symbol,
            bars,
            capital=capital,
            min_win_rate=min_win_rate,
        )
    except YahooFinanceProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _strategy_screen_response(screen)


@router.get("/{symbol}/backtest", response_model=OptionsBacktestResponse)
def options_backtest(
    symbol: SymbolPath,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    style: OptionsStyle = OptionsStyle.ZERO_DTE,
    days: BacktestDays = 1825,
    capital: BacktestCapital = Decimal("10000"),
) -> OptionsBacktestResponse:
    """Run the modeled 0DTE/weekly options strategy over real underlying history."""

    today = datetime.now(UTC).date()
    request = HistoricalMarketDataRequest(
        instrument_id=instrument_id(symbol),
        symbol=symbol.upper(),
        start=today - timedelta(days=days),
        end=today + timedelta(days=1),
    )
    try:
        bars = market_data.fetch_daily_history(request).bars
        backtester = OptionsBacktester(
            agents=create_default_agents(),
            engine=MasterDecisionEngine(),
            style=style,
            initial_capital=capital,
        )
        result = backtester.run(request.instrument_id, request.symbol, bars)
    except YahooFinanceProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _backtest_response(result)


def _strategy_screen_response(screen: OptionsStrategyScreen) -> OptionsStrategyScreenResponse:
    recommended = next((item.style.value for item in screen.results if item.recommended), None)
    return OptionsStrategyScreenResponse(
        symbol=screen.symbol,
        modeled=True,
        pricing_note=PRICING_NOTE,
        min_win_rate=screen.min_win_rate,
        recommended_style=recommended,
        results=tuple(
            OptionsStrategyScoreResponse(
                style=item.style.value,
                recommended=item.recommended,
                meets_threshold=item.meets_threshold,
                final_equity=item.result.final_equity,
                win_rate=item.result.metrics.win_rate,
                trade_count=item.result.metrics.trade_count,
                winning_trades=item.result.metrics.winning_trades,
                losing_trades=item.result.metrics.losing_trades,
                total_return=item.result.metrics.total_return,
                max_drawdown=item.result.metrics.max_drawdown,
                profit_factor=item.result.metrics.profit_factor,
            )
            for item in screen.results
        ),
    )


def _trade_response(trade: OptionsTrade) -> OptionsTradeResponse:
    return OptionsTradeResponse(
        option_side=trade.option_side.value,
        strike=trade.strike,
        expiration=trade.expiration,
        entry_at=trade.entry_at,
        entry_underlying=trade.entry_underlying,
        entry_premium=trade.entry_premium,
        contracts=trade.contracts,
        exit_at=trade.exit_at,
        exit_underlying=trade.exit_underlying,
        exit_premium=trade.exit_premium,
        realized_pnl=trade.realized_pnl,
        entry_reason=trade.entry_reason,
        exit_reason=trade.exit_reason,
    )


def _backtest_response(result: OptionsBacktestResult) -> OptionsBacktestResponse:
    return OptionsBacktestResponse(
        symbol=result.symbol,
        style=result.style.value,
        modeled=True,
        pricing_note=PRICING_NOTE,
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        metrics=OptionsBacktestMetricsResponse(
            win_rate=result.metrics.win_rate,
            trade_count=result.metrics.trade_count,
            winning_trades=result.metrics.winning_trades,
            losing_trades=result.metrics.losing_trades,
            total_return=result.metrics.total_return,
            max_drawdown=result.metrics.max_drawdown,
            profit_factor=result.metrics.profit_factor,
        ),
        equity_curve=tuple(
            OptionsEquityPointResponse(on=point.on, equity=point.equity)
            for point in result.equity_curve
        ),
        trades=tuple(_trade_response(trade) for trade in result.trades),
        next_signal=_decision_response(result.next_signal) if result.next_signal else None,
    )


def _research_response(research: OptionsResearch, max_dte: int) -> OptionsResearchResponse:
    planned = tuple(_planned_trade_response(trade) for trade in research.planned_trades)
    return OptionsResearchResponse(
        symbol=research.symbol,
        underlying_price=research.underlying_price,
        as_of=research.as_of,
        max_dte=max_dte,
        near_term_count=research.near_term_count,
        zero_dte_count=research.zero_dte_count,
        signal=_decision_response(research.signal),
        unusual_activity=tuple(
            UnusualContractResponse(
                contract=_contract_response(item.contract),
                volume_oi_ratio=item.volume_oi_ratio,
            )
            for item in research.unusual_activity
        ),
        planned_trades=planned,
        today_planned_trades=tuple(
            trade for trade in planned if trade.contract.days_to_expiry == 0
        ),
        future_planned_trades=tuple(
            trade for trade in planned if trade.contract.days_to_expiry > 0
        ),
    )
