"""Compare every named strategy variant on one symbol's real history.

Fetches the symbol's bars once and runs each strategy variant (see
``strategies.py``) against the exact same data, reporting each one's real
backtested win rate side by side. Flags which variants (if any) clear a
win-rate threshold — an honest result: some symbols/windows may have zero
qualifying strategies, and that is reported as-is rather than forced.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.app.application.strategies import (
    STRATEGIES,
    StrategyDefinition,
    build_strategy_backtest_service,
)
from backend.app.domain.entities import BacktestRun, Bar, MasterDecision
from backend.app.domain.errors import DomainValidationError

DEFAULT_WIN_RATE_THRESHOLD = Decimal("0.8")
_NAMESPACE = uuid5(NAMESPACE_URL, "ai-quant-platform/strategy-screener")


@dataclass(frozen=True, slots=True)
class StrategyScreenResult:
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
    next_signal: MasterDecision | None


@dataclass(frozen=True, slots=True)
class StrategyScreen:
    symbol: str
    win_rate_threshold: Decimal
    results: tuple[StrategyScreenResult, ...]
    qualifying_count: int


class StrategyScreenerService:
    """Backtest every registered strategy variant against one shared bar set."""

    def screen(
        self,
        symbol: str,
        instrument_id: UUID,
        bars: Sequence[Bar],
        capital: Decimal,
        win_rate_threshold: Decimal = DEFAULT_WIN_RATE_THRESHOLD,
    ) -> StrategyScreen:
        if not bars:
            raise DomainValidationError("strategy screen requires at least one bar")
        results = tuple(
            self._run_one(strategy, symbol, instrument_id, bars, capital, win_rate_threshold)
            for strategy in STRATEGIES
        )
        ranked = tuple(sorted(results, key=lambda item: item.win_rate, reverse=True))
        qualifying = sum(1 for item in ranked if item.meets_threshold)
        return StrategyScreen(
            symbol=symbol,
            win_rate_threshold=win_rate_threshold,
            results=ranked,
            qualifying_count=qualifying,
        )

    def _run_one(
        self,
        strategy: StrategyDefinition,
        symbol: str,
        instrument_id: UUID,
        bars: Sequence[Bar],
        capital: Decimal,
        win_rate_threshold: Decimal,
    ) -> StrategyScreenResult:
        run = BacktestRun(
            id=uuid5(_NAMESPACE, f"{symbol}:{strategy.key}"),
            strategy_name=strategy.key,
            instrument_id=instrument_id,
            start_date=bars[0].timestamp.date(),
            end_date=bars[-1].timestamp.date(),
            initial_capital=capital,
            commission=Decimal("0"),
            slippage_bps=Decimal("1"),
            benchmark_symbol=symbol,
        )
        service = build_strategy_backtest_service(strategy)
        outcome = service.run(run, bars)
        result = outcome.result
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
            end_equity / start_equity - Decimal("1")
            if start_equity != Decimal("0")
            else Decimal("0")
        )
        return StrategyScreenResult(
            key=strategy.key,
            label=strategy.label,
            description=strategy.description,
            trade_count=result.metrics.trade_count,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=result.metrics.win_rate,
            total_return=total_return,
            max_drawdown=result.metrics.max_drawdown,
            meets_threshold=result.metrics.win_rate >= win_rate_threshold,
            next_signal=outcome.latest_decision,
        )
