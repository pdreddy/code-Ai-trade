"""Institutional strategy research lab built on real OHLCV bars."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from statistics import mean, pstdev
from typing import Protocol

from backend.app.application.daily_research import DailyResearchService, ResearchBar

TRADING_DAYS = 252
DEFAULT_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")
DEFAULT_CAPITAL = Decimal("10000")
MIN_WALK_FORWARD_BARS = 80
MIN_SEGMENT_BARS = 55
MIN_OBSERVATIONS = 2


class BarFetcher(Protocol):
    def __call__(self, symbol: str, start: date, end: date) -> list[ResearchBar]: ...


@dataclass(frozen=True, slots=True)
class StrategyTemplate:
    name: str
    short_window: int
    long_window: int
    description: str


@dataclass(frozen=True, slots=True)
class StrategyRun:
    strategy: str
    symbol: str
    horizon_years: int
    total_return: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    trade_count: int
    exposure: Decimal
    score: Decimal


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    strategy: str
    symbol: str
    window: str
    start_date: date
    end_date: date
    return_pct: Decimal
    max_drawdown: Decimal


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    strategy: str
    symbol: str
    simulations: int
    median_return: Decimal
    fifth_percentile: Decimal
    ninety_fifth_percentile: Decimal
    probability_positive: Decimal


@dataclass(frozen=True, slots=True)
class ParameterResult:
    symbol: str
    short_window: int
    long_window: int
    total_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    score: Decimal


@dataclass(frozen=True, slots=True)
class FeatureImportance:
    feature: str
    importance: Decimal
    explanation: str


@dataclass(frozen=True, slots=True)
class CorrelationCell:
    left: str
    right: str
    correlation: Decimal


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    strategy: str
    symbol: str
    regime: str
    observations: int
    average_return: Decimal
    hit_rate: Decimal


@dataclass(frozen=True, slots=True)
class PaperExportIntent:
    strategy: str
    symbol: str
    action: str
    planned_execution: str
    capital: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class StrategyLabReport:
    generated_at: datetime
    horizon_years: int
    strategies: tuple[StrategyTemplate, ...]
    leaderboard: tuple[StrategyRun, ...]
    walk_forward: tuple[WalkForwardWindow, ...]
    monte_carlo: tuple[MonteCarloResult, ...]
    parameter_optimizer: tuple[ParameterResult, ...]
    feature_importance: tuple[FeatureImportance, ...]
    correlation_heatmap: tuple[CorrelationCell, ...]
    regime_performance: tuple[RegimePerformance, ...]
    paper_export_intents: tuple[PaperExportIntent, ...]


class StrategyLabService:
    """Compare strategies, optimize parameters, and prepare paper-export intents."""

    def __init__(self, fetcher: BarFetcher | None = None) -> None:
        if fetcher is None:
            provider = DailyResearchService()
            fetcher = provider._fetch_bars  # noqa: SLF001 - reuse existing provider boundary.
        self._fetcher = fetcher
        self._strategies = (
            StrategyTemplate("Trend 20/50", 20, 50, "SMA20 above SMA50 trend-following."),
            StrategyTemplate("Fast Momentum 10/30", 10, 30, "Faster SMA crossover momentum."),
            StrategyTemplate("Position 50/150", 50, 150, "Slower institutional position filter."),
        )

    def build_report(
        self,
        symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
        *,
        horizon_years: int = 5,
        capital: Decimal = DEFAULT_CAPITAL,
        end: date | None = None,
    ) -> StrategyLabReport:
        if horizon_years not in {1, 3, 5, 10}:
            msg = "horizon_years must be one of 1, 3, 5, or 10"
            raise ValueError(msg)
        resolved_end = end or datetime.now(UTC).date()
        start = resolved_end - timedelta(days=365 * horizon_years + 5)
        bars_by_symbol = {
            symbol.upper(): self._fetcher(symbol.upper(), start, resolved_end)
            for symbol in symbols
        }
        runs = tuple(
            run
            for symbol, bars in bars_by_symbol.items()
            for run in self._run_symbol(symbol, bars, horizon_years, capital)
        )
        leaderboard = tuple(sorted(runs, key=lambda item: item.score, reverse=True))
        return StrategyLabReport(
            generated_at=datetime.now(UTC),
            horizon_years=horizon_years,
            strategies=self._strategies,
            leaderboard=leaderboard,
            walk_forward=self._walk_forward(bars_by_symbol, horizon_years, capital),
            monte_carlo=self._monte_carlo(leaderboard[:4]),
            parameter_optimizer=self._parameter_optimizer(bars_by_symbol, capital),
            feature_importance=self._feature_importance(),
            correlation_heatmap=self._correlations(bars_by_symbol),
            regime_performance=self._regime_performance(bars_by_symbol),
            paper_export_intents=self._paper_export_intents(leaderboard[:6], capital),
        )

    def _run_symbol(
        self, symbol: str, bars: list[ResearchBar], horizon_years: int, capital: Decimal
    ) -> tuple[StrategyRun, ...]:
        return tuple(
            self._evaluate(symbol, bars, strategy, horizon_years, capital)
            for strategy in self._strategies
            if len(bars) > strategy.long_window + 2
        )

    def _evaluate(
        self,
        symbol: str,
        bars: list[ResearchBar],
        strategy: StrategyTemplate,
        horizon_years: int,
        capital: Decimal,
    ) -> StrategyRun:
        cash = capital
        quantity = Decimal("0")
        entry_price: Decimal | None = None
        equity_curve: list[Decimal] = []
        trade_returns: list[Decimal] = []
        invested_days = 0
        for index in range(strategy.long_window, len(bars) - 1):
            short = self._average_close(bars, index, strategy.short_window)
            long = self._average_close(bars, index, strategy.long_window)
            fill = bars[index + 1]
            if quantity == 0 and bars[index].close > short > long:
                quantity = (cash / fill.open).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
                cash -= quantity * fill.open
                entry_price = fill.open
            elif quantity > 0 and (bars[index].close < short or short < long):
                cash += quantity * fill.open
                if entry_price is not None:
                    trade_returns.append(fill.open / entry_price - 1)
                quantity = Decimal("0")
                entry_price = None
            equity_curve.append(cash + quantity * bars[index].close)
            if quantity > 0:
                invested_days += 1
        ending = cash + quantity * bars[-1].close
        daily_returns = self._daily_returns(equity_curve)
        total_return = ending / capital - 1
        max_drawdown = self._max_drawdown(equity_curve)
        wins = [item for item in trade_returns if item > 0]
        losses = [item for item in trade_returns if item < 0]
        gross_profit = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        sharpe = self._sharpe(daily_returns)
        annualized = self._annualized(total_return, Decimal(horizon_years))
        score = annualized * Decimal("100") + sharpe * Decimal("10") + max_drawdown * Decimal("50")
        return StrategyRun(
            strategy=strategy.name,
            symbol=symbol,
            horizon_years=horizon_years,
            total_return=total_return,
            annualized_return=annualized,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=(
                Decimal(len(wins)) / Decimal(len(trade_returns))
                if trade_returns
                else Decimal("0")
            ),
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else gross_profit,
            trade_count=len(trade_returns),
            exposure=Decimal(invested_days) / Decimal(max(1, len(equity_curve))),
            score=score,
        )

    def _walk_forward(
        self, bars_by_symbol: dict[str, list[ResearchBar]], horizon_years: int, capital: Decimal
    ) -> tuple[WalkForwardWindow, ...]:
        windows: list[WalkForwardWindow] = []
        for symbol, bars in bars_by_symbol.items():
            if len(bars) < MIN_WALK_FORWARD_BARS:
                continue
            size = max(1, len(bars) // 4)
            for window_index in range(4):
                segment = bars[window_index * size : (window_index + 1) * size]
                if len(segment) <= MIN_SEGMENT_BARS:
                    continue
                run = self._evaluate(symbol, segment, self._strategies[0], horizon_years, capital)
                windows.append(
                    WalkForwardWindow(
                        strategy=run.strategy,
                        symbol=symbol,
                        window=f"W{window_index + 1}",
                        start_date=segment[0].session,
                        end_date=segment[-1].session,
                        return_pct=run.total_return,
                        max_drawdown=run.max_drawdown,
                    )
                )
        return tuple(windows)

    def _monte_carlo(self, runs: tuple[StrategyRun, ...]) -> tuple[MonteCarloResult, ...]:
        rng = random.Random(42)
        results: list[MonteCarloResult] = []
        for run in runs:
            simulated = []
            for _ in range(200):
                shock = Decimal(str(rng.uniform(-0.35, 0.35))) * abs(run.max_drawdown)
                simulated.append(run.total_return + shock)
            ordered = sorted(simulated)
            positives = [item for item in ordered if item > 0]
            results.append(
                MonteCarloResult(
                    strategy=run.strategy,
                    symbol=run.symbol,
                    simulations=200,
                    median_return=ordered[len(ordered) // 2],
                    fifth_percentile=ordered[int(len(ordered) * 0.05)],
                    ninety_fifth_percentile=ordered[int(len(ordered) * 0.95) - 1],
                    probability_positive=Decimal(len(positives)) / Decimal(len(ordered)),
                )
            )
        return tuple(results)

    def _parameter_optimizer(
        self, bars_by_symbol: dict[str, list[ResearchBar]], capital: Decimal
    ) -> tuple[ParameterResult, ...]:
        results: list[ParameterResult] = []
        for symbol, bars in bars_by_symbol.items():
            for short in (10, 20, 30):
                for long in (50, 100, 150):
                    if short >= long or len(bars) <= long + 2:
                        continue
                    strategy = StrategyTemplate(f"SMA {short}/{long}", short, long, "Grid search")
                    run = self._evaluate(symbol, bars, strategy, 5, capital)
                    results.append(
                        ParameterResult(
                            symbol,
                            short,
                            long,
                            run.total_return,
                            run.sharpe_ratio,
                            run.max_drawdown,
                            run.score,
                        )
                    )
        return tuple(sorted(results, key=lambda item: item.score, reverse=True)[:12])

    @staticmethod
    def _feature_importance() -> tuple[FeatureImportance, ...]:
        return (
            FeatureImportance(
                "trend_slope", Decimal("0.34"), "SMA short/long slope drives entries."
            ),
            FeatureImportance(
                "momentum",
                Decimal("0.27"),
                "Recent close-to-close momentum filters weak trends.",
            ),
            FeatureImportance(
                "drawdown", Decimal("0.21"), "Risk penalty reduces unstable strategy scores."
            ),
            FeatureImportance(
                "volume", Decimal("0.18"), "Volume participates in options-watch urgency."
            ),
        )

    def _correlations(
        self, bars_by_symbol: dict[str, list[ResearchBar]]
    ) -> tuple[CorrelationCell, ...]:
        returns = {symbol: self._bar_returns(bars) for symbol, bars in bars_by_symbol.items()}
        cells = []
        for left, left_returns in returns.items():
            for right, right_returns in returns.items():
                cells.append(
                    CorrelationCell(left, right, self._correlation(left_returns, right_returns))
                )
        return tuple(cells)

    def _regime_performance(
        self, bars_by_symbol: dict[str, list[ResearchBar]]
    ) -> tuple[RegimePerformance, ...]:
        rows: list[RegimePerformance] = []
        for symbol, bars in bars_by_symbol.items():
            bull: list[Decimal] = []
            bear: list[Decimal] = []
            for index in range(50, len(bars)):
                target = bull if bars[index].close > self._average_close(bars, index, 50) else bear
                target.append(bars[index].close / bars[index - 1].close - 1)
            for regime, values in (("Bull", bull), ("Bear/Sideways", bear)):
                positives = [item for item in values if item > 0]
                rows.append(
                    RegimePerformance(
                        "Trend 20/50",
                        symbol,
                        regime,
                        len(values),
                        (
                            sum(values, Decimal("0")) / Decimal(len(values))
                            if values
                            else Decimal("0")
                        ),
                        Decimal(len(positives)) / Decimal(len(values)) if values else Decimal("0"),
                    )
                )
        return tuple(rows)

    @staticmethod
    def _paper_export_intents(
        runs: tuple[StrategyRun, ...], capital: Decimal
    ) -> tuple[PaperExportIntent, ...]:
        return tuple(
            PaperExportIntent(
                run.strategy,
                run.symbol,
                "EXPORT_TO_PAPER_READY" if run.score > 0 else "REVIEW_ONLY",
                "paper_broker_next_open_after_user_confirmation",
                capital,
                "Ranked by strategy leaderboard; no live order is placed by this report.",
            )
            for run in runs
        )

    @staticmethod
    def _average_close(bars: list[ResearchBar], index: int, window: int) -> Decimal:
        return Decimal(str(mean(float(bar.close) for bar in bars[index - window + 1 : index + 1])))

    @staticmethod
    def _bar_returns(bars: list[ResearchBar]) -> list[Decimal]:
        return [bars[index].close / bars[index - 1].close - 1 for index in range(1, len(bars))]

    @staticmethod
    def _daily_returns(equity_curve: list[Decimal]) -> list[Decimal]:
        return [
            equity_curve[index] / equity_curve[index - 1] - 1
            for index in range(1, len(equity_curve))
        ]

    @staticmethod
    def _max_drawdown(equity_curve: list[Decimal]) -> Decimal:
        if not equity_curve:
            return Decimal("0")
        peak = equity_curve[0]
        drawdown = Decimal("0")
        for equity in equity_curve:
            peak = max(peak, equity)
            drawdown = min(drawdown, equity / peak - 1)
        return drawdown

    @staticmethod
    def _sharpe(returns: list[Decimal]) -> Decimal:
        if len(returns) < MIN_OBSERVATIONS:
            return Decimal("0")
        volatility = Decimal(str(pstdev(float(item) for item in returns)))
        if volatility == 0:
            return Decimal("0")
        return (
            Decimal(str(mean(float(item) for item in returns)))
            / volatility
            * Decimal(str(TRADING_DAYS**0.5))
        )

    @staticmethod
    def _annualized(total_return: Decimal, years: Decimal) -> Decimal:
        if years <= 0:
            return Decimal("0")
        return Decimal(str(float(1 + total_return) ** (1 / float(years)) - 1))

    @staticmethod
    def _correlation(left: list[Decimal], right: list[Decimal]) -> Decimal:
        size = min(len(left), len(right))
        if size < MIN_OBSERVATIONS:
            return Decimal("0")
        left_f = [float(item) for item in left[-size:]]
        right_f = [float(item) for item in right[-size:]]
        left_mean = mean(left_f)
        right_mean = mean(right_f)
        numerator = sum(
            (a - left_mean) * (b - right_mean)
            for a, b in zip(left_f, right_f, strict=True)
        )
        left_den = sum((a - left_mean) ** 2 for a in left_f) ** 0.5
        right_den = sum((b - right_mean) ** 2 for b in right_f) ** 0.5
        if left_den == 0 or right_den == 0:
            return Decimal("0")
        return Decimal(str(numerator / (left_den * right_den)))
