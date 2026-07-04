"""Run the modeled options backtester across a universe with one capital base.

Mirrors ``portfolio_execution.py`` (the equity version) but for the options
strategy: capital is split equally across symbols, each sleeve runs the
Black-Scholes-modeled 0DTE or weekly backtest, and the sleeves are aggregated
into one options portfolio (equity curve, blended success rate, every trade).

The backtester always force-closes a still-open position at the end of its
window (see ``options_backtesting.py``), so every sleeve's final equity is pure
cash — there is no "current open position" concept here. This is a historical,
modeled track record, not a live position feed; the forward-looking live paper
ledger (real chain quotes) is a separate feature.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import MasterDecisionEngine
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import (
    OptionsBacktester,
    OptionsBacktestResult,
    OptionsStyle,
    OptionsTrade,
)
from backend.app.application.portfolio_execution import instrument_id
from backend.app.domain.entities import MasterDecision
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import HistoricalMarketDataRequest


@dataclass(frozen=True, slots=True)
class OptionsSleeveTrade:
    symbol: str
    trade: OptionsTrade


@dataclass(frozen=True, slots=True)
class OptionsSleeveResult:
    symbol: str
    style: OptionsStyle
    allocated: Decimal
    final_equity: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    next_signal: MasterDecision | None
    trades: tuple[OptionsSleeveTrade, ...]
    equity_by_day: tuple[tuple[date, Decimal], ...]


@dataclass(frozen=True, slots=True)
class OptionsSleeveError:
    symbol: str
    detail: str


@dataclass(frozen=True, slots=True)
class OptionsEquityPoint:
    on: date
    equity: Decimal


@dataclass(frozen=True, slots=True)
class OptionsPortfolioExecution:
    style: OptionsStyle
    initial_capital: Decimal
    total_equity: Decimal
    total_pnl: Decimal
    total_return: Decimal
    success_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    max_drawdown: Decimal
    sleeves: tuple[OptionsSleeveResult, ...]
    trades: tuple[OptionsSleeveTrade, ...]
    equity_curve: tuple[OptionsEquityPoint, ...]
    errors: tuple[OptionsSleeveError, ...]


@dataclass(slots=True)
class OptionsPortfolioExecutionService:
    """Run the modeled options backtester across a universe and aggregate it."""

    market_data: MarketDataService
    max_workers: int = 8

    def run(
        self,
        symbols: Sequence[str],
        capital: Decimal,
        days: int,
        style: OptionsStyle,
    ) -> OptionsPortfolioExecution:
        universe = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        if not universe:
            raise DomainValidationError("options portfolio execution requires at least one symbol")
        per_symbol_capital = (capital / Decimal(len(universe))).quantize(Decimal("0.01"))

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            outcomes = list(
                pool.map(
                    lambda symbol: self._run_sleeve(symbol, per_symbol_capital, days, style),
                    universe,
                )
            )

        sleeves = tuple(item for item in outcomes if isinstance(item, OptionsSleeveResult))
        errors = tuple(item for item in outcomes if isinstance(item, OptionsSleeveError))
        return self._aggregate(style, capital, sleeves, errors)

    def _run_sleeve(
        self, symbol: str, capital: Decimal, days: int, style: OptionsStyle
    ) -> OptionsSleeveResult | OptionsSleeveError:
        try:
            request = self._history_request(symbol, days)
            bars = self.market_data.fetch_daily_history(request).bars
            if not bars:
                return OptionsSleeveError(symbol=symbol, detail="no bars returned by provider")
            backtester = OptionsBacktester(
                agents=create_default_agents(),
                engine=MasterDecisionEngine(),
                style=style,
                initial_capital=capital,
            )
            result: OptionsBacktestResult = backtester.run(request.instrument_id, symbol, bars)
        except DomainValidationError as exc:
            return OptionsSleeveError(symbol=symbol, detail=str(exc))
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not sink the portfolio
            return OptionsSleeveError(symbol=symbol, detail=str(exc) or exc.__class__.__name__)

        return OptionsSleeveResult(
            symbol=symbol,
            style=style,
            allocated=capital,
            final_equity=result.final_equity,
            trade_count=result.metrics.trade_count,
            winning_trades=result.metrics.winning_trades,
            losing_trades=result.metrics.losing_trades,
            win_rate=result.metrics.win_rate,
            next_signal=result.next_signal,
            trades=tuple(
                OptionsSleeveTrade(symbol=symbol, trade=trade) for trade in result.trades
            ),
            equity_by_day=tuple((point.on, point.equity) for point in result.equity_curve),
        )

    def _aggregate(
        self,
        style: OptionsStyle,
        initial_capital: Decimal,
        sleeves: Sequence[OptionsSleeveResult],
        errors: Sequence[OptionsSleeveError],
    ) -> OptionsPortfolioExecution:
        total_equity = sum((sleeve.final_equity for sleeve in sleeves), Decimal("0"))
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
        return OptionsPortfolioExecution(
            style=style,
            initial_capital=initial_capital,
            total_equity=total_equity,
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


def _combined_equity_curve(
    sleeves: Sequence[OptionsSleeveResult],
) -> tuple[OptionsEquityPoint, ...]:
    """Sum sleeve equity onto a shared calendar, forward-filling gaps per sleeve."""

    all_days = sorted({day for sleeve in sleeves for day, _ in sleeve.equity_by_day})
    if not all_days:
        return ()
    lookups = [dict(sleeve.equity_by_day) for sleeve in sleeves]
    last_values = [sleeve.allocated for sleeve in sleeves]
    curve: list[OptionsEquityPoint] = []
    for day in all_days:
        total = Decimal("0")
        for index, lookup in enumerate(lookups):
            if day in lookup:
                last_values[index] = lookup[day]
            total += last_values[index]
        curve.append(OptionsEquityPoint(on=day, equity=total))
    return tuple(curve)


def _max_drawdown(equity_curve: Sequence[OptionsEquityPoint]) -> Decimal:
    if not equity_curve:
        return Decimal("0")
    high_watermark = equity_curve[0].equity
    worst = Decimal("0")
    for point in equity_curve:
        high_watermark = max(high_watermark, point.equity)
        if high_watermark > Decimal("0"):
            worst = min(worst, point.equity / high_watermark - Decimal("1"))
    return worst
