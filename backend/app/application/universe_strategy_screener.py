"""Compare every named strategy variant, pooled across the whole universe.

The single-symbol screener (``strategy_screener.py``) answers "which variant
wins on this one ticker's history" — a small sample that can look great or
terrible by chance. This runs the same real backtests across every symbol in
the universe and pools each variant's wins/losses into one aggregate real win
rate, which is what "the best real strategy" honestly means: not cherry-picked
off a single favorable symbol. Symbols whose history can't be fetched are
skipped and reported, never faked. If no variant clears the threshold on
enough real trades, that is reported as-is.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.app.application.market_data import MarketDataService
from backend.app.application.portfolio_execution import instrument_id
from backend.app.application.strategies import STRATEGIES, build_strategy_backtest_service
from backend.app.application.strategy_screener import DEFAULT_WIN_RATE_THRESHOLD
from backend.app.domain.entities import BacktestRun
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import HistoricalMarketDataRequest

# A strategy needs a real sample of closed trades pooled across the universe
# before its win rate is trustworthy enough to call "the best" — otherwise a
# variant that only fired twice could look like a false 100% winner.
MIN_POOLED_TRADES = 20

_PerSymbolRow = tuple[str, int, int, int]  # strategy key, trade count, wins, losses


@dataclass(frozen=True, slots=True)
class UniverseStrategyResult:
    key: str
    label: str
    description: str
    symbols_evaluated: int
    trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    meets_threshold: bool


@dataclass(frozen=True, slots=True)
class UniverseSymbolError:
    symbol: str
    detail: str


@dataclass(frozen=True, slots=True)
class UniverseStrategyScreen:
    universe: tuple[str, ...]
    win_rate_threshold: Decimal
    results: tuple[UniverseStrategyResult, ...]
    qualifying_count: int
    best_key: str
    errors: tuple[UniverseSymbolError, ...]


@dataclass(slots=True)
class UniverseStrategyScreenerService:
    market_data: MarketDataService
    max_workers: int = 12

    def screen(
        self,
        symbols: Sequence[str],
        days: int,
        win_rate_threshold: Decimal = DEFAULT_WIN_RATE_THRESHOLD,
    ) -> UniverseStrategyScreen:
        universe = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        if not universe:
            raise DomainValidationError("universe strategy screen requires at least one symbol")

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            outcomes = list(pool.map(lambda symbol: self._per_symbol(symbol, days), universe))

        errors = tuple(
            UniverseSymbolError(symbol=symbol, detail=detail)
            for symbol, (detail, _) in zip(universe, outcomes, strict=True)
            if detail is not None
        )

        # symbols evaluated, trade count, wins, losses — pooled per strategy key.
        pooled: dict[str, list[int]] = {strategy.key: [0, 0, 0, 0] for strategy in STRATEGIES}
        for _, rows in outcomes:
            if rows is None:
                continue
            for key, trade_count, winning, losing in rows:
                bucket = pooled[key]
                bucket[0] += 1
                bucket[1] += trade_count
                bucket[2] += winning
                bucket[3] += losing

        results = [
            _pooled_result(
                strategy.key, strategy.label, strategy.description, pooled, win_rate_threshold
            )
            for strategy in STRATEGIES
        ]
        ranked = tuple(sorted(results, key=_rank_key, reverse=True))
        qualifying = sum(1 for item in ranked if item.meets_threshold)
        best_key = next((item.key for item in ranked if item.meets_threshold), "master")
        return UniverseStrategyScreen(
            universe=universe,
            win_rate_threshold=win_rate_threshold,
            results=ranked,
            qualifying_count=qualifying,
            best_key=best_key,
            errors=errors,
        )

    def _per_symbol(
        self, symbol: str, days: int
    ) -> tuple[str | None, list[_PerSymbolRow] | None]:
        try:
            request = self._history_request(symbol, days)
            bars = self.market_data.fetch_daily_history(request).bars
            if not bars:
                return "no bars returned by provider", None

            rows: list[_PerSymbolRow] = []
            for strategy in STRATEGIES:
                run = BacktestRun(
                    id=instrument_id(f"{symbol}:universe-screen:{strategy.key}"),
                    strategy_name=strategy.key,
                    instrument_id=request.instrument_id,
                    start_date=bars[0].timestamp.date(),
                    end_date=bars[-1].timestamp.date(),
                    initial_capital=Decimal("10000"),
                    commission=Decimal("0"),
                    slippage_bps=Decimal("1"),
                    benchmark_symbol=symbol,
                )
                service = build_strategy_backtest_service(strategy)
                outcome = service.run(run, bars)
                realized = [
                    trade.trade.realized_pnl
                    for trade in outcome.result.trades
                    if trade.trade.realized_pnl is not None
                ]
                winning = sum(1 for pnl in realized if pnl > Decimal("0"))
                losing = sum(1 for pnl in realized if pnl < Decimal("0"))
                rows.append((strategy.key, outcome.result.metrics.trade_count, winning, losing))
            return None, rows
        except DomainValidationError as exc:
            return str(exc), None
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not sink the screen
            return str(exc) or exc.__class__.__name__, None

    def _history_request(self, symbol: str, days: int) -> HistoricalMarketDataRequest:
        today = datetime.now(UTC).date()
        return HistoricalMarketDataRequest(
            instrument_id=instrument_id(symbol),
            symbol=symbol.upper(),
            start=today - timedelta(days=days),
            end=today + timedelta(days=1),
        )


def _pooled_result(
    key: str,
    label: str,
    description: str,
    pooled: dict[str, list[int]],
    win_rate_threshold: Decimal,
) -> UniverseStrategyResult:
    symbols_evaluated, trade_count, winning, losing = pooled[key]
    closed = winning + losing
    win_rate = Decimal(winning) / Decimal(closed) if closed else Decimal("0")
    return UniverseStrategyResult(
        key=key,
        label=label,
        description=description,
        symbols_evaluated=symbols_evaluated,
        trade_count=trade_count,
        winning_trades=winning,
        losing_trades=losing,
        win_rate=win_rate,
        meets_threshold=win_rate >= win_rate_threshold and closed >= MIN_POOLED_TRADES,
    )


def _rank_key(item: UniverseStrategyResult) -> Decimal:
    # Push variants without enough of a real sample to the bottom rather than
    # letting a lucky, tiny sample outrank a well-evidenced result.
    if item.winning_trades + item.losing_trades < MIN_POOLED_TRADES:
        return Decimal("-1")
    return item.win_rate
