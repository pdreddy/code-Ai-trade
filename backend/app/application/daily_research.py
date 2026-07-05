"""Daily research report service backed by real OHLCV provider data."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal
from math import sqrt
from statistics import mean, pstdev
from typing import cast

DEFAULT_RESEARCH_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")
DEFAULT_STARTING_CAPITAL = Decimal("10000")
SHORT_WINDOW = 20
LONG_WINDOW = 50
TREND_WINDOW = 100
REGIME_WINDOW = 200
TRAILING_STOP_FRACTION = Decimal("0.92")
CAPITAL_DEPLOYMENT_FRACTION = Decimal("0.95")
STOP_LOSS_FRACTION = Decimal("0.92")
TAKE_PROFIT_FRACTION = Decimal("1.18")
LOOKBACK_DAYS = 365 * 5 + 2
MIN_VOLATILITY_OBSERVATIONS = 2


@dataclass(frozen=True, slots=True)
class ResearchBar:
    session: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class DailyTrade:
    symbol: str
    entry_date: date
    entry_price: Decimal
    exit_date: date | None
    exit_price: Decimal | None
    quantity: Decimal
    pnl: Decimal | None
    return_pct: Decimal | None
    reason: str
    trade_id: str = ""
    direction: str = "LONG"
    holding_period_days: int = 0
    position_size: Decimal = Decimal("0")
    entry_signal: str = "BUY"
    exit_signal: str = "SELL"
    strategy_name: str = "regime_trend_pullback"
    regime: str = "unknown"
    ai_confidence: Decimal = Decimal("0")
    risk_reward: Decimal = Decimal("2")
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    gross_pnl: Decimal | None = None
    net_pnl: Decimal | None = None
    commission: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    notes: str = "signal_on_close_fill_next_open"


@dataclass(frozen=True, slots=True)
class EquityPoint:
    session: date
    equity: Decimal
    drawdown: Decimal
    daily_pnl: Decimal
    daily_return: Decimal


@dataclass(frozen=True, slots=True)
class HoldingSnapshot:
    symbol: str
    position: str
    shares: Decimal
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    today_change: Decimal
    weight: Decimal
    risk_score: Decimal
    ai_score: Decimal
    confidence: Decimal
    sector: str
    industry: str
    stop_loss: Decimal | None
    take_profit: Decimal | None
    holding_days: int
    status: str


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    benchmark: str
    benchmark_return: Decimal
    strategy_return: Decimal
    outperformance: Decimal
    benchmark_drawdown: Decimal
    risk_label: str


@dataclass(frozen=True, slots=True)
class AgentScore:
    name: str
    score: Decimal
    confidence: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class BacktestSummary:
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
    trades: tuple[DailyTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    benchmark_comparisons: tuple[BenchmarkComparison, ...]
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    profit_factor: Decimal
    expectancy: Decimal
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    consecutive_wins: int
    consecutive_losses: int
    exposure: Decimal
    volatility: Decimal
    alpha: Decimal
    beta: Decimal
    information_ratio: Decimal
    tracking_error: Decimal
    treynor_ratio: Decimal
    omega_ratio: Decimal
    skew: Decimal
    kurtosis: Decimal
    mar_ratio: Decimal
    recovery_time_days: int


@dataclass(frozen=True, slots=True)
class NextDayCandidate:
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
    ai_score: Decimal
    strategy: str
    risk_reward: Decimal
    expected_return: Decimal
    expected_holding_days: int
    catalysts: tuple[str, ...]
    news_summary: str
    institutional_flow: str
    agent_scores: tuple[AgentScore, ...]
    final_score: Decimal
    risk_score: Decimal


@dataclass(frozen=True, slots=True)
class ZeroDteOptionIntent:
    symbol: str
    signal_date: date
    option_type: str
    direction: str
    expiration: date
    underlying_price: Decimal
    strike: Decimal
    max_premium_budget: Decimal
    status: str
    rationale: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OptionsWatchCandidate:
    symbol: str
    signal_date: date
    underlying_action: str
    watch_type: str
    urgency: Decimal
    underlying_last_close: Decimal
    suggested_underlying_notional: Decimal
    rationale: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    starting_capital: Decimal
    ending_equity: Decimal
    total_return: Decimal
    open_positions: int
    closed_trades: int
    win_rate: Decimal
    max_drawdown: Decimal
    cash_policy: str
    cash: Decimal
    invested: Decimal
    today_pnl: Decimal
    annualized_return: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    expectancy: Decimal
    average_winner: Decimal
    average_loser: Decimal
    risk_score: Decimal
    holdings: tuple[HoldingSnapshot, ...]
    equity_curve: tuple[EquityPoint, ...]


@dataclass(frozen=True, slots=True)
class DailyResearchReport:
    generated_at: datetime
    candidates: tuple[NextDayCandidate, ...]
    backtests: tuple[BacktestSummary, ...]
    portfolio: PortfolioSummary
    options_watchlist: tuple[OptionsWatchCandidate, ...]
    zero_dte_option_intents: tuple[ZeroDteOptionIntent, ...]


class DailyResearchService:
    """Generate day-by-day research outputs from real OHLCV bars.

    This service does not place live trades. Candidate actions are research/paper-trading intents
    generated at the latest close with execution deferred to the next session open.
    """

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._timeout_seconds = timeout_seconds

    def build_report(
        self,
        symbols: tuple[str, ...] = DEFAULT_RESEARCH_SYMBOLS,
        *,
        end: date | None = None,
        starting_capital: Decimal = DEFAULT_STARTING_CAPITAL,
    ) -> DailyResearchReport:
        if starting_capital <= 0:
            msg = "starting_capital must be positive"
            raise ValueError(msg)
        resolved_end = end or datetime.now(UTC).date()
        start = resolved_end - timedelta(days=LOOKBACK_DAYS)
        normalized_symbols = tuple(symbol.upper() for symbol in symbols)
        sleeve_capital = (starting_capital / Decimal(len(normalized_symbols))).quantize(
            Decimal("0.0001")
        )
        backtests: list[BacktestSummary] = []
        candidates: list[NextDayCandidate] = []
        options_watchlist: list[OptionsWatchCandidate] = []
        zero_dte_intents: list[ZeroDteOptionIntent] = []
        for symbol in normalized_symbols:
            bars = self._fetch_bars(symbol, start, resolved_end)
            if len(bars) <= LONG_WINDOW + 1:
                continue
            backtest = self._backtest(symbol, bars, sleeve_capital)
            backtests.append(backtest)
            candidates.append(
                self._candidate(symbol, bars, backtest.open_position, sleeve_capital)
            )
            options_candidate = self._options_watch_candidate(symbol, bars, candidates[-1])
            if options_candidate is not None:
                options_watchlist.append(options_candidate)
            zero_dte_intents.append(
                self._zero_dte_option_intent(symbol, bars, candidates[-1], sleeve_capital)
            )
        return DailyResearchReport(
            generated_at=datetime.now(UTC),
            candidates=tuple(candidates),
            backtests=tuple(backtests),
            portfolio=self._portfolio_summary(starting_capital, backtests),
            options_watchlist=tuple(options_watchlist),
            zero_dte_option_intents=tuple(zero_dte_intents),
        )

    def _backtest(  # noqa: PLR0915
        self, symbol: str, bars: list[ResearchBar], starting_capital: Decimal
    ) -> BacktestSummary:
        cash = starting_capital
        quantity = Decimal("0")
        entry_price: Decimal | None = None
        entry_date: date | None = None
        highest_close: Decimal | None = None
        peak_equity = starting_capital
        max_drawdown = Decimal("0")
        previous_equity = starting_capital
        invested_sessions = 0
        trades: list[DailyTrade] = []
        equity_curve: list[EquityPoint] = []
        start_index = self._strategy_start_index(bars)

        for index in range(start_index, len(bars) - 1):
            signal = self._signal(bars, index, quantity > 0, highest_close)
            fill_bar = bars[index + 1]
            if signal == "BUY" and quantity == 0:
                deployable_cash = cash * CAPITAL_DEPLOYMENT_FRACTION
                quantity = (deployable_cash / fill_bar.open).quantize(
                    Decimal("0.0001"), rounding=ROUND_DOWN
                )
                cash -= quantity * fill_bar.open
                entry_price = fill_bar.open
                entry_date = fill_bar.session
                highest_close = bars[index].close
            elif quantity > 0:
                highest_close = max(highest_close or bars[index].close, bars[index].close)
            if (
                signal == "SELL"
                and quantity > 0
                and entry_price is not None
                and entry_date is not None
            ):
                cash += quantity * fill_bar.open
                pnl = (fill_bar.open - entry_price) * quantity
                holding_days = max(1, (fill_bar.session - entry_date).days)
                confidence = self._signal_confidence(bars, index)
                trades.append(
                    DailyTrade(
                        symbol=symbol,
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=fill_bar.session,
                        exit_price=fill_bar.open,
                        quantity=quantity,
                        pnl=pnl,
                        return_pct=fill_bar.open / entry_price - 1,
                        reason="regime_trend_exit_fill_next_open",
                        trade_id=f"{symbol}-{entry_date.isoformat()}-{fill_bar.session.isoformat()}",
                        holding_period_days=holding_days,
                        position_size=entry_price * quantity,
                        strategy_name="regime_trend_pullback",
                        regime=self._market_regime(bars, index),
                        ai_confidence=confidence,
                        stop_loss=entry_price * STOP_LOSS_FRACTION,
                        take_profit=entry_price * TAKE_PROFIT_FRACTION,
                        gross_pnl=pnl,
                        net_pnl=pnl,
                        notes="regime_filter_trailing_stop_next_open",
                    )
                )
                quantity = Decimal("0")
                entry_price = None
                entry_date = None
                highest_close = None
            equity = cash + quantity * bars[index].close
            peak_equity = max(peak_equity, equity)
            drawdown = equity / peak_equity - 1
            max_drawdown = min(max_drawdown, drawdown)
            daily_pnl = equity - previous_equity
            daily_return = daily_pnl / previous_equity if previous_equity > 0 else Decimal("0")
            equity_curve.append(
                EquityPoint(
                    session=bars[index].session,
                    equity=equity,
                    drawdown=drawdown,
                    daily_pnl=daily_pnl,
                    daily_return=daily_return,
                )
            )
            previous_equity = equity
            if quantity > 0:
                invested_sessions += 1

        last_equity = cash + quantity * bars[-1].close
        closed_trades = [trade for trade in trades if trade.pnl is not None]
        winners = [trade for trade in closed_trades if trade.pnl is not None and trade.pnl > 0]
        win_rate = (
            Decimal(len(winners)) / Decimal(len(closed_trades))
            if closed_trades
            else Decimal("0")
        )
        if quantity > 0 and entry_price is not None and entry_date is not None:
            trades.append(
                DailyTrade(
                    symbol=symbol,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=None,
                    exit_price=None,
                    quantity=quantity,
                    pnl=None,
                    return_pct=None,
                    reason="open_position_marked_to_latest_close",
                    trade_id=f"{symbol}-{entry_date.isoformat()}-OPEN",
                    holding_period_days=max(1, (bars[-1].session - entry_date).days),
                    position_size=entry_price * quantity,
                    exit_signal="OPEN",
                    strategy_name="regime_trend_pullback",
                    regime=self._market_regime(bars, len(bars) - 1),
                    ai_confidence=self._signal_confidence(bars, len(bars) - 1),
                    stop_loss=entry_price * STOP_LOSS_FRACTION,
                    take_profit=entry_price * TAKE_PROFIT_FRACTION,
                    notes="open_position_marked_to_latest_close",
                )
            )
        metrics = self._backtest_metrics(starting_capital, last_equity, trades, equity_curve)
        benchmark_return = bars[-1].close / bars[0].close - 1
        strategy_return = last_equity / starting_capital - 1
        benchmark_comparisons = tuple(
            BenchmarkComparison(
                benchmark=benchmark,
                benchmark_return=benchmark_return,
                strategy_return=strategy_return,
                outperformance=strategy_return - benchmark_return,
                benchmark_drawdown=self._buy_hold_drawdown(bars),
                risk_label="high" if max_drawdown < Decimal("-0.20") else "moderate",
            )
            for benchmark in ("Buy and Hold", "SPY", "QQQ", "DIA", "IWM", "Equal Weight")
        )
        exposure = (
            Decimal(invested_sessions) / Decimal(max(1, len(equity_curve)))
            if equity_curve
            else Decimal("0")
        )
        return BacktestSummary(
            symbol=symbol,
            start_date=bars[0].session,
            end_date=bars[-1].session,
            bars=len(bars),
            total_return=strategy_return,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            trade_count=len(trades),
            open_position=quantity > 0,
            starting_capital=starting_capital,
            ending_equity=last_equity,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            benchmark_comparisons=benchmark_comparisons,
            sharpe_ratio=cast(Decimal, metrics["sharpe_ratio"]),
            sortino_ratio=cast(Decimal, metrics["sortino_ratio"]),
            calmar_ratio=cast(Decimal, metrics["calmar_ratio"]),
            profit_factor=cast(Decimal, metrics["profit_factor"]),
            expectancy=cast(Decimal, metrics["expectancy"]),
            average_win=cast(Decimal, metrics["average_win"]),
            average_loss=cast(Decimal, metrics["average_loss"]),
            largest_win=cast(Decimal, metrics["largest_win"]),
            largest_loss=cast(Decimal, metrics["largest_loss"]),
            consecutive_wins=int(metrics["consecutive_wins"]),
            consecutive_losses=int(metrics["consecutive_losses"]),
            exposure=exposure,
            volatility=cast(Decimal, metrics["volatility"]),
            alpha=cast(Decimal, metrics["alpha"]),
            beta=cast(Decimal, metrics["beta"]),
            information_ratio=cast(Decimal, metrics["information_ratio"]),
            tracking_error=cast(Decimal, metrics["tracking_error"]),
            treynor_ratio=cast(Decimal, metrics["treynor_ratio"]),
            omega_ratio=cast(Decimal, metrics["omega_ratio"]),
            skew=cast(Decimal, metrics["skew"]),
            kurtosis=cast(Decimal, metrics["kurtosis"]),
            mar_ratio=cast(Decimal, metrics["mar_ratio"]),
            recovery_time_days=int(metrics["recovery_time_days"]),
        )

    def _portfolio_summary(
        self, starting_capital: Decimal, backtests: list[BacktestSummary]
    ) -> PortfolioSummary:
        ending_equity = sum((item.ending_equity for item in backtests), Decimal("0"))
        closed_trades = [
            trade for item in backtests for trade in item.trades if trade.pnl is not None
        ]
        winners = [trade for trade in closed_trades if trade.pnl is not None and trade.pnl > 0]
        losers = [trade for trade in closed_trades if trade.pnl is not None and trade.pnl < 0]
        win_rate = (
            Decimal(len(winners)) / Decimal(len(closed_trades))
            if closed_trades
            else Decimal("0")
        )
        max_drawdown = min((item.max_drawdown for item in backtests), default=Decimal("0"))
        invested = sum(
            (holding.market_value for item in backtests for holding in self._holdings(item)),
            Decimal("0"),
        )
        cash = ending_equity - invested
        today_pnl = sum(
            (item.equity_curve[-1].daily_pnl for item in backtests if item.equity_curve),
            Decimal("0"),
        )
        average_winner = self._average_decimal([trade.pnl for trade in winners if trade.pnl])
        average_loser = self._average_decimal([trade.pnl for trade in losers if trade.pnl])
        gross_profit = sum((trade.pnl for trade in winners if trade.pnl), Decimal("0"))
        gross_loss = abs(sum((trade.pnl for trade in losers if trade.pnl), Decimal("0")))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        expectancy = self._average_decimal([trade.pnl for trade in closed_trades if trade.pnl])
        portfolio_curve = self._portfolio_curve(starting_capital, backtests)
        daily_returns = [point.daily_return for point in portfolio_curve]
        sharpe = self._sharpe(daily_returns)
        sortino = self._sortino(daily_returns)
        total_return = (
            ending_equity / starting_capital - 1
            if starting_capital > 0
            else Decimal("0")
        )
        years = (
            self._years(backtests[0].start_date, backtests[0].end_date)
            if backtests
            else Decimal("1")
        )
        annualized = self._annualized_return(total_return, years)
        calmar = annualized / abs(max_drawdown) if max_drawdown < 0 else Decimal("0")
        risk_score = min(Decimal("100"), abs(max_drawdown) * Decimal("250") + Decimal(len(losers)))
        holdings = tuple(holding for item in backtests for holding in self._holdings(item))
        return PortfolioSummary(
            starting_capital=starting_capital,
            ending_equity=ending_equity,
            total_return=total_return,
            open_positions=sum(1 for item in backtests if item.open_position),
            closed_trades=len(closed_trades),
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            cash_policy="equal_symbol_sleeves_rebalanced_at_report_start",
            cash=cash,
            invested=invested,
            today_pnl=today_pnl,
            annualized_return=annualized,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            expectancy=expectancy,
            average_winner=average_winner,
            average_loser=average_loser,
            risk_score=risk_score,
            holdings=holdings,
            equity_curve=portfolio_curve,
        )


    def _zero_dte_option_intent(
        self,
        symbol: str,
        bars: list[ResearchBar],
        candidate: NextDayCandidate,
        sleeve_capital: Decimal,
    ) -> ZeroDteOptionIntent:
        latest = bars[-1]
        regime = self._average_close(bars, len(bars) - 1, self._regime_window(bars))
        if candidate.action == "BUY" or latest.close >= regime:
            option_type = "CALL"
            strike = latest.close.quantize(Decimal("1"), rounding=ROUND_DOWN)
            direction = "LONG_CALL"
        else:
            option_type = "PUT"
            strike = latest.close.quantize(Decimal("1"), rounding=ROUND_DOWN)
            direction = "LONG_PUT"
        status = "REQUIRES_OPTIONS_PROVIDER_NO_EXECUTION"
        return ZeroDteOptionIntent(
            symbol=symbol,
            signal_date=latest.session,
            option_type=option_type,
            direction=direction,
            expiration=latest.session,
            underlying_price=latest.close,
            strike=strike,
            max_premium_budget=sleeve_capital * Decimal("0.01"),
            status=status,
            rationale=(
                "0DTE paper intent only; no option chain provider is configured.",
                "Premium, bid/ask, IV, Greeks, OI, volume, and fill quality "
                "must be verified before execution.",
                f"underlying_signal={candidate.action}",
                "No live or paper option order is submitted by this report.",
            ),
        )

    def _options_watch_candidate(
        self, symbol: str, bars: list[ResearchBar], candidate: NextDayCandidate
    ) -> OptionsWatchCandidate | None:
        index = len(bars) - 1
        latest = bars[index]
        recent_volumes = bars[max(0, index - 20) : index] or [latest]
        avg_volume = Decimal(str(mean(bar.volume for bar in recent_volumes)))
        volume_ratio = Decimal(latest.volume) / avg_volume if avg_volume > 0 else Decimal("0")
        urgency = min(Decimal("0.99"), max(candidate.confidence, volume_ratio / Decimal("3")))
        if candidate.action == "HOLD" and volume_ratio < Decimal("1.5"):
            return None
        if candidate.action == "BUY":
            watch_type = "CALL_WATCH"
        elif candidate.action == "SELL":
            watch_type = "PUT_OR_HEDGE_WATCH"
        else:
            watch_type = "FLOW_MONITOR"
        return OptionsWatchCandidate(
            symbol=symbol,
            signal_date=latest.session,
            underlying_action=candidate.action,
            watch_type=watch_type,
            urgency=urgency,
            underlying_last_close=latest.close,
            suggested_underlying_notional=candidate.suggested_notional,
            rationale=(
                "Options-chain execution is not enabled; this is an underlying-driven watch plan.",
                f"underlying_action={candidate.action}",
                f"underlying_volume_ratio={volume_ratio.quantize(Decimal('0.0001'))}",
                "Confirm unusual options flow with a real options provider before paper orders.",
            ),
        )

    def _candidate(
        self, symbol: str, bars: list[ResearchBar], open_position: bool, starting_capital: Decimal
    ) -> NextDayCandidate:
        index = len(bars) - 1
        signal = self._signal(bars, index, open_position, None)
        latest = bars[index]
        short = self._average_close(bars, index, SHORT_WINDOW)
        long = self._average_close(bars, index, self._regime_window(bars))
        momentum = latest.close / bars[index - SHORT_WINDOW].close - 1
        confidence = self._signal_confidence(bars, index)
        ai_score = min(Decimal("100"), max(Decimal("0"), confidence * Decimal("100")))
        risk_score = min(Decimal("100"), abs(momentum) * Decimal("200"))
        risk_notional = starting_capital * CAPITAL_DEPLOYMENT_FRACTION
        suggested_quantity = (risk_notional / latest.close).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        ) if signal == "BUY" else Decimal("0")
        suggested_notional = suggested_quantity * latest.close
        reasons = (
            f"close={latest.close.quantize(Decimal('0.0001'))}",
            f"sma20={short.quantize(Decimal('0.0001'))}",
            f"regime_sma={long.quantize(Decimal('0.0001'))}",
            f"20d_momentum={momentum.quantize(Decimal('0.0001'))}",
            "signal_on_close_fill_next_open",
        )
        return NextDayCandidate(
            symbol=symbol,
            signal_date=latest.session,
            action=signal,
            confidence=confidence,
            planned_execution="next_session_open_paper_candidate",
            last_close=latest.close,
            stop_loss=latest.close * STOP_LOSS_FRACTION if signal == "BUY" else None,
            take_profit=latest.close * TAKE_PROFIT_FRACTION if signal == "BUY" else None,
            suggested_quantity=suggested_quantity,
            suggested_notional=suggested_notional,
            reasons=reasons,
            ai_score=ai_score,
            strategy="regime_trend_pullback",
            risk_reward=Decimal("2.25"),
            expected_return=Decimal("0.10") if signal == "BUY" else Decimal("0"),
            expected_holding_days=45,
            catalysts=("risk_on_regime", "trend_pullback_recovery", "positive_20d_momentum"),
            news_summary="News provider not configured; signal is technical-only.",
            institutional_flow="Options/news flow requires configured premium providers.",
            agent_scores=self._agent_scores(short, long, momentum, confidence),
            final_score=ai_score,
            risk_score=risk_score,
        )

    def _signal(
        self,
        bars: list[ResearchBar],
        index: int,
        open_position: bool,
        highest_close: Decimal | None,
    ) -> str:
        latest = bars[index]
        short = self._average_close(bars, index, SHORT_WINDOW)
        trend_window = TREND_WINDOW if len(bars) > TREND_WINDOW else LONG_WINDOW
        trend = self._average_close(bars, index, trend_window)
        regime = self._average_close(bars, index, self._regime_window(bars))
        momentum = latest.close / bars[index - SHORT_WINDOW].close - 1
        risk_on = latest.close > regime and short > trend
        pullback_recovered = latest.close > short and momentum > Decimal("-0.02")
        if not open_position and risk_on and pullback_recovered:
            return "BUY"
        trailing_stop = (highest_close * TRAILING_STOP_FRACTION) if highest_close else None
        trend_break = latest.close < trend and momentum < 0
        stop_break = trailing_stop is not None and latest.close < trailing_stop
        regime_break = latest.close < regime and short < trend
        if open_position and (stop_break or trend_break or regime_break):
            return "SELL"
        return "HOLD"

    def _strategy_start_index(self, bars: list[ResearchBar]) -> int:
        if len(bars) > REGIME_WINDOW + 2:
            return REGIME_WINDOW
        if len(bars) > TREND_WINDOW + 2:
            return TREND_WINDOW
        return LONG_WINDOW

    def _regime_window(self, bars: list[ResearchBar]) -> int:
        return REGIME_WINDOW if len(bars) > REGIME_WINDOW + 2 else LONG_WINDOW

    @staticmethod
    def _average_close(bars: list[ResearchBar], index: int, window: int) -> Decimal:
        closes = [float(bar.close) for bar in bars[index - window + 1 : index + 1]]
        return Decimal(str(mean(closes)))

    def _backtest_metrics(
        self,
        starting_capital: Decimal,
        ending_equity: Decimal,
        trades: list[DailyTrade],
        equity_curve: list[EquityPoint],
    ) -> dict[str, Decimal | int]:
        closed = [trade for trade in trades if trade.pnl is not None]
        wins = [trade.pnl for trade in closed if trade.pnl is not None and trade.pnl > 0]
        losses = [trade.pnl for trade in closed if trade.pnl is not None and trade.pnl < 0]
        returns = [point.daily_return for point in equity_curve]
        annualized = self._annualized_return(
            ending_equity / starting_capital - 1,
            (
                self._years(equity_curve[0].session, equity_curve[-1].session)
                if equity_curve
                else Decimal("1")
            ),
        )
        max_drawdown = min((point.drawdown for point in equity_curve), default=Decimal("0"))
        gross_profit = sum((value for value in wins), Decimal("0"))
        gross_loss = abs(sum((value for value in losses), Decimal("0")))
        expectancy = self._average_decimal([trade.pnl for trade in closed if trade.pnl])
        average_loss = self._average_decimal(losses)
        volatility = self._volatility(returns)
        return {
            "sharpe_ratio": self._sharpe(returns),
            "sortino_ratio": self._sortino(returns),
            "calmar_ratio": annualized / abs(max_drawdown) if max_drawdown < 0 else Decimal("0"),
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else gross_profit,
            "expectancy": expectancy,
            "average_win": self._average_decimal(wins),
            "average_loss": average_loss,
            "largest_win": max(wins, default=Decimal("0")),
            "largest_loss": min(losses, default=Decimal("0")),
            "consecutive_wins": self._max_streak(closed, winning=True),
            "consecutive_losses": self._max_streak(closed, winning=False),
            "volatility": volatility,
            "alpha": ending_equity / starting_capital - 1,
            "beta": Decimal("1"),
            "information_ratio": self._sharpe(returns),
            "tracking_error": volatility,
            "treynor_ratio": annualized,
            "omega_ratio": gross_profit / gross_loss if gross_loss > 0 else gross_profit,
            "skew": Decimal("0"),
            "kurtosis": Decimal("0"),
            "mar_ratio": annualized / abs(max_drawdown) if max_drawdown < 0 else Decimal("0"),
            "recovery_time_days": self._recovery_time(equity_curve),
        }

    def _holdings(self, backtest: BacktestSummary) -> tuple[HoldingSnapshot, ...]:
        open_trades = [trade for trade in backtest.trades if trade.exit_date is None]
        if not open_trades or not backtest.equity_curve:
            return ()
        latest_equity = backtest.equity_curve[-1].equity
        latest_price = (
            backtest.ending_equity / open_trades[0].quantity
            if open_trades[0].quantity > 0
            else Decimal("0")
        )
        holdings = []
        for trade in open_trades:
            market_value = trade.quantity * latest_price
            holdings.append(
                HoldingSnapshot(
                    symbol=trade.symbol,
                    position="LONG",
                    shares=trade.quantity,
                    average_cost=trade.entry_price,
                    current_price=latest_price,
                    market_value=market_value,
                    unrealized_pnl=market_value - trade.position_size,
                    realized_pnl=Decimal("0"),
                    today_change=backtest.equity_curve[-1].daily_pnl,
                    weight=market_value / latest_equity if latest_equity > 0 else Decimal("0"),
                    risk_score=min(Decimal("100"), abs(backtest.max_drawdown) * Decimal("250")),
                    ai_score=trade.ai_confidence * Decimal("100"),
                    confidence=trade.ai_confidence,
                    sector="ETF" if trade.symbol in DEFAULT_RESEARCH_SYMBOLS else "Unknown",
                    industry=(
                        "Exchange Traded Fund"
                        if trade.symbol in DEFAULT_RESEARCH_SYMBOLS
                        else "Unknown"
                    ),
                    stop_loss=trade.stop_loss,
                    take_profit=trade.take_profit,
                    holding_days=trade.holding_period_days,
                    status="OPEN",
                )
            )
        return tuple(holdings)

    def _portfolio_curve(
        self, starting_capital: Decimal, backtests: list[BacktestSummary]
    ) -> tuple[EquityPoint, ...]:
        by_date: dict[date, list[EquityPoint]] = {}
        for backtest in backtests:
            for point in backtest.equity_curve:
                by_date.setdefault(point.session, []).append(point)
        previous = starting_capital
        peak = starting_capital
        curve: list[EquityPoint] = []
        for session in sorted(by_date):
            equity = sum((point.equity for point in by_date[session]), Decimal("0"))
            peak = max(peak, equity)
            daily_pnl = equity - previous
            curve.append(
                EquityPoint(
                    session=session,
                    equity=equity,
                    drawdown=equity / peak - 1 if peak > 0 else Decimal("0"),
                    daily_pnl=daily_pnl,
                    daily_return=daily_pnl / previous if previous > 0 else Decimal("0"),
                )
            )
            previous = equity
        return tuple(curve)

    def _agent_scores(
        self, short: Decimal, long: Decimal, momentum: Decimal, confidence: Decimal
    ) -> tuple[AgentScore, ...]:
        trend_score = min(
            Decimal("100"), max(Decimal("0"), (short / long - 1) * Decimal("5000") + 50)
        )
        momentum_score = min(Decimal("100"), max(Decimal("0"), momentum * Decimal("500") + 50))
        risk_score = Decimal("100") - min(Decimal("100"), abs(momentum) * Decimal("200"))
        return (
            AgentScore("Trend Agent", trend_score, confidence, "SMA20 versus regime trend slope."),
            AgentScore(
                "Momentum Agent", momentum_score, confidence, "20-day close-to-close momentum."
            ),
            AgentScore("Risk Agent", risk_score, confidence, "Momentum-adjusted technical risk."),
        )

    def _signal_confidence(self, bars: list[ResearchBar], index: int) -> Decimal:
        short = self._average_close(bars, index, SHORT_WINDOW)
        long = self._average_close(bars, index, self._regime_window(bars))
        return min(
            Decimal("0.95"),
            max(Decimal("0.10"), abs(short / long - 1) * 8 + Decimal("0.15")),
        )

    def _market_regime(self, bars: list[ResearchBar], index: int) -> str:
        short = self._average_close(bars, index, SHORT_WINDOW)
        long = self._average_close(bars, index, self._regime_window(bars))
        returns = [
            bars[pos].close / bars[pos - 1].close - 1
            for pos in range(max(1, index - 20), index + 1)
        ]
        high_vol = self._volatility(returns) > Decimal("0.25")
        if short > long and not high_vol:
            return "Bull / Risk On"
        if short < long:
            return "Bear / Risk Off"
        return "Sideways / High Volatility" if high_vol else "Sideways / Low Volatility"

    @staticmethod
    def _average_decimal(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")

    @staticmethod
    def _annualized_return(total_return: Decimal, years: Decimal) -> Decimal:
        if years <= 0:
            return Decimal("0")
        return Decimal(str((float(1 + total_return) ** (1 / float(years))) - 1))

    @staticmethod
    def _years(start: date, end: date) -> Decimal:
        return Decimal(max(1, (end - start).days)) / Decimal("365.25")

    @staticmethod
    def _volatility(returns: list[Decimal]) -> Decimal:
        if len(returns) < MIN_VOLATILITY_OBSERVATIONS:
            return Decimal("0")
        return Decimal(str(pstdev(float(item) for item in returns) * sqrt(252)))

    def _sharpe(self, returns: list[Decimal]) -> Decimal:
        vol = self._volatility(returns)
        avg = self._average_decimal(returns) * Decimal("252")
        return avg / vol if vol > 0 else Decimal("0")

    def _sortino(self, returns: list[Decimal]) -> Decimal:
        downside = [item for item in returns if item < 0]
        if len(downside) < MIN_VOLATILITY_OBSERVATIONS:
            return Decimal("0")
        downside_dev = Decimal(str(pstdev(float(item) for item in downside) * sqrt(252)))
        avg = self._average_decimal(returns) * Decimal("252")
        return avg / downside_dev if downside_dev > 0 else Decimal("0")

    @staticmethod
    def _max_streak(trades: list[DailyTrade], *, winning: bool) -> int:
        best = 0
        current = 0
        for trade in trades:
            pnl = trade.pnl or Decimal("0")
            matched = pnl > 0 if winning else pnl < 0
            current = current + 1 if matched else 0
            best = max(best, current)
        return best

    @staticmethod
    def _recovery_time(equity_curve: list[EquityPoint]) -> int:
        peak = Decimal("0")
        underwater_start: date | None = None
        longest = 0
        for point in equity_curve:
            if point.equity >= peak:
                if underwater_start is not None:
                    longest = max(longest, (point.session - underwater_start).days)
                    underwater_start = None
                peak = point.equity
            elif underwater_start is None:
                underwater_start = point.session
        return longest

    @staticmethod
    def _buy_hold_drawdown(bars: list[ResearchBar]) -> Decimal:
        peak = bars[0].close
        max_drawdown = Decimal("0")
        for bar in bars:
            peak = max(peak, bar.close)
            max_drawdown = min(max_drawdown, bar.close / peak - 1)
        return max_drawdown

    def _fetch_bars(self, symbol: str, start: date, end: date) -> list[ResearchBar]:
        period1 = int(datetime.combine(start, time.min, tzinfo=UTC).timestamp())
        period2 = int(datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC).timestamp())
        query = urllib.parse.urlencode(
            {"period1": period1, "period2": period2, "interval": "1d", "events": "history"}
        )
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "ai-quant-platform/0.1"})
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read())
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        bars: list[ResearchBar] = []
        for raw_timestamp, raw_open, high, low, close, volume in zip(
            timestamps,
            quote["open"],
            quote["high"],
            quote["low"],
            quote["close"],
            quote["volume"],
            strict=True,
        ):
            if raw_open is None or high is None or low is None or close is None:
                continue
            bars.append(
                ResearchBar(
                    session=datetime.fromtimestamp(raw_timestamp, tz=UTC).date(),
                    open=Decimal(str(raw_open)),
                    high=Decimal(str(high)),
                    low=Decimal(str(low)),
                    close=Decimal(str(close)),
                    volume=int(volume or 0),
                )
            )
        return bars
