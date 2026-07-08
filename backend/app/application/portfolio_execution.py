"""Execute the AI strategy across a universe with one shared capital base.

The service allocates the account equally across the requested symbols, runs the
same signal-on-close / fill-next-open strategy that powers the single-symbol
backtest on each sleeve, and aggregates the sleeves into one portfolio: combined
equity, cash-versus-invested split, blended success rate, every executed trade,
and the forward-looking next signal per symbol (the upcoming planned trades).

No synthetic prices are used — each sleeve is driven by the same real provider
history as the rest of the platform. Symbols whose upstream data is unavailable
are reported as errors rather than silently dropped or faked.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.backtesting import EventDrivenBacktester
from backend.app.application.decision_engine import MasterDecisionEngine
from backend.app.application.market_data import MarketDataService
from backend.app.application.strategies import get_strategy
from backend.app.application.strategy_backtest import StrategyBacktestService
from backend.app.domain.entities import BacktestRun, MasterDecision, Trade
from backend.app.domain.enums import OrderSide, OrderState
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import HistoricalMarketDataRequest

_INSTRUMENT_NAMESPACE = uuid5(NAMESPACE_URL, "ai-quant-platform/instrument")


def instrument_id(symbol: str) -> UUID:
    return uuid5(_INSTRUMENT_NAMESPACE, symbol.upper())


@dataclass(frozen=True, slots=True)
class SleeveTrade:
    symbol: str
    trade: Trade
    entry_reason: str
    exit_reason: str | None


@dataclass(frozen=True, slots=True)
class SleeveResult:
    symbol: str
    allocated: Decimal
    current_value: Decimal
    realized_pnl: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    holding: bool
    last_close: Decimal
    next_signal: MasterDecision
    trades: tuple[SleeveTrade, ...]
    equity_by_day: tuple[tuple[date, Decimal], ...]


@dataclass(frozen=True, slots=True)
class SleeveError:
    symbol: str
    detail: str


@dataclass(frozen=True, slots=True)
class EquityPoint:
    on: date
    equity: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioExecution:
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
    sleeves: tuple[SleeveResult, ...]
    trades: tuple[SleeveTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    errors: tuple[SleeveError, ...]


@dataclass(slots=True)
class PortfolioExecutionService:
    """Run the strategy across a universe and aggregate the sleeves into a portfolio."""

    market_data: MarketDataService
    max_workers: int = 12

    def run(self, symbols: Sequence[str], capital: Decimal, days: int) -> PortfolioExecution:
        universe = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        if not universe:
            raise DomainValidationError("portfolio execution requires at least one symbol")
        per_symbol_capital = (capital / Decimal(len(universe))).quantize(Decimal("0.01"))

        outcomes = self._run_universe(universe, per_symbol_capital, days)
        sleeves = tuple(item for item in outcomes if isinstance(item, SleeveResult))
        errors = tuple(item for item in outcomes if isinstance(item, SleeveError))
        return self._aggregate(capital, sleeves, errors)

    def _run_universe(
        self, universe: Sequence[str], per_symbol_capital: Decimal, days: int
    ) -> list[SleeveResult | SleeveError]:
        # Provider history is I/O bound, so fan the sleeves out across a small pool.
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(
                pool.map(
                    lambda symbol: self._run_sleeve(symbol, per_symbol_capital, days),
                    universe,
                )
            )

    def _run_sleeve(self, symbol: str, capital: Decimal, days: int) -> SleeveResult | SleeveError:
        try:
            request = self._history_request(symbol, days)
            bars = self.market_data.fetch_daily_history(request).bars
            if not bars:
                return SleeveError(symbol=symbol, detail="no bars returned by provider")
            run = BacktestRun(
                id=uuid5(_INSTRUMENT_NAMESPACE, f"{symbol}:portfolio"),
                strategy_name="ai_master_decision",
                instrument_id=request.instrument_id,
                start_date=bars[0].timestamp.date(),
                end_date=bars[-1].timestamp.date(),
                initial_capital=capital,
                commission=Decimal("0"),
                slippage_bps=Decimal("1"),
                benchmark_symbol=symbol,
            )
            portfolio_strategy = get_strategy("guarded_momentum")
            strategy = StrategyBacktestService(
                agents=create_default_agents(),
                engine=MasterDecisionEngine(policy=portfolio_strategy.policy),
                backtester=EventDrivenBacktester(),
                agent_names=portfolio_strategy.agent_names,
            )
            outcome = strategy.run(run, bars)
        except DomainValidationError as exc:
            return SleeveError(symbol=symbol, detail=str(exc))
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not sink the portfolio
            return SleeveError(symbol=symbol, detail=str(exc) or exc.__class__.__name__)

        result = outcome.result
        realized = [
            trade.trade.realized_pnl
            for trade in result.trades
            if trade.trade.realized_pnl is not None
        ]
        winning = sum(1 for pnl in realized if pnl > Decimal("0"))
        losing = sum(1 for pnl in realized if pnl < Decimal("0"))
        filled_buys = sum(
            1
            for order in result.orders
            if order.state is OrderState.FILLED and order.side is OrderSide.BUY
        )
        filled_sells = sum(
            1
            for order in result.orders
            if order.state is OrderState.FILLED and order.side is OrderSide.SELL
        )
        # latest_decision is always populated when the sleeve has bars.
        assert outcome.latest_decision is not None
        return SleeveResult(
            symbol=symbol,
            allocated=capital,
            current_value=result.equity_curve[-1].equity,
            realized_pnl=sum(realized, Decimal("0")),
            trade_count=result.metrics.trade_count,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=result.metrics.win_rate,
            holding=filled_buys > filled_sells,
            last_close=bars[-1].close.value,
            next_signal=outcome.latest_decision,
            trades=tuple(
                SleeveTrade(
                    symbol=symbol,
                    trade=item.trade,
                    entry_reason=item.entry_reason,
                    exit_reason=item.exit_reason,
                )
                for item in result.trades
            ),
            equity_by_day=tuple(
                (point.timestamp.date(), point.equity) for point in result.equity_curve
            ),
        )

    def _aggregate(
        self,
        initial_capital: Decimal,
        sleeves: Sequence[SleeveResult],
        errors: Sequence[SleeveError],
    ) -> PortfolioExecution:
        total_equity = sum((sleeve.current_value for sleeve in sleeves), Decimal("0"))
        invested = sum((sleeve.current_value for sleeve in sleeves if sleeve.holding), Decimal("0"))
        cash = total_equity - invested
        deployed = sum((sleeve.allocated for sleeve in sleeves), Decimal("0"))
        total_pnl = total_equity - deployed
        total_return = (
            total_equity / deployed - Decimal("1") if deployed > Decimal("0") else Decimal("0")
        )
        winning = sum(sleeve.winning_trades for sleeve in sleeves)
        losing = sum(sleeve.losing_trades for sleeve in sleeves)
        trade_count = sum(sleeve.trade_count for sleeve in sleeves)
        closed = winning + losing
        success_rate = Decimal(winning) / Decimal(closed) if closed else Decimal("0")
        trades = tuple(
            sorted(
                (trade for sleeve in sleeves for trade in sleeve.trades),
                key=lambda item: item.trade.entry_at,
            )
        )
        equity_curve = _combined_equity_curve(sleeves)
        return PortfolioExecution(
            initial_capital=initial_capital,
            total_equity=total_equity,
            cash=cash,
            invested=invested,
            total_pnl=total_pnl,
            total_return=total_return,
            success_rate=success_rate,
            trade_count=trade_count,
            winning_trades=winning,
            losing_trades=losing,
            max_drawdown=_max_drawdown(equity_curve),
            sleeves=tuple(sleeves),
            trades=trades,
            equity_curve=equity_curve,
            errors=tuple(errors),
        )

    def _history_request(self, symbol: str, days: int) -> HistoricalMarketDataRequest:
        today = datetime.now(UTC).date()
        return HistoricalMarketDataRequest(
            instrument_id=instrument_id(symbol),
            symbol=symbol.upper(),
            start=today - timedelta(days=days),
            end=today + timedelta(days=1),
        )


def _combined_equity_curve(sleeves: Sequence[SleeveResult]) -> tuple[EquityPoint, ...]:
    """Sum sleeve equity onto a shared calendar, forward-filling gaps per sleeve.

    Sleeves may not share identical trading days (halts, listings), so each sleeve
    carries its last known equity forward across the union of all dates. Before a
    sleeve's first bar it contributes its allocated capital, so the portfolio starts
    at the full deployed amount rather than jumping as sleeves come online.
    """

    all_days = sorted({day for sleeve in sleeves for day, _ in sleeve.equity_by_day})
    if not all_days:
        return ()
    lookups = [dict(sleeve.equity_by_day) for sleeve in sleeves]
    last_values = [sleeve.allocated for sleeve in sleeves]
    curve: list[EquityPoint] = []
    for day in all_days:
        total = Decimal("0")
        for index, lookup in enumerate(lookups):
            if day in lookup:
                last_values[index] = lookup[day]
            total += last_values[index]
        curve.append(EquityPoint(on=day, equity=total))
    return tuple(curve)


def _max_drawdown(equity_curve: Sequence[EquityPoint]) -> Decimal:
    if not equity_curve:
        return Decimal("0")
    high_watermark = equity_curve[0].equity
    worst = Decimal("0")
    for point in equity_curve:
        high_watermark = max(high_watermark, point.equity)
        if high_watermark > Decimal("0"):
            worst = min(worst, point.equity / high_watermark - Decimal("1"))
    return worst
