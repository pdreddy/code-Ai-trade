"""Daily research report service backed by real OHLCV provider data."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_DOWN, Decimal
from statistics import mean

DEFAULT_RESEARCH_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")
DEFAULT_STARTING_CAPITAL = Decimal("10000")
SHORT_WINDOW = 20
LONG_WINDOW = 50
LOOKBACK_DAYS = 365 * 5 + 2


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


@dataclass(frozen=True, slots=True)
class DailyResearchReport:
    generated_at: datetime
    candidates: tuple[NextDayCandidate, ...]
    backtests: tuple[BacktestSummary, ...]
    portfolio: PortfolioSummary
    options_watchlist: tuple[OptionsWatchCandidate, ...]


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
        return DailyResearchReport(
            generated_at=datetime.now(UTC),
            candidates=tuple(candidates),
            backtests=tuple(backtests),
            portfolio=self._portfolio_summary(starting_capital, backtests),
            options_watchlist=tuple(options_watchlist),
        )

    def _backtest(
        self, symbol: str, bars: list[ResearchBar], starting_capital: Decimal
    ) -> BacktestSummary:
        cash = starting_capital
        quantity = Decimal("0")
        entry_price: Decimal | None = None
        entry_date: date | None = None
        peak_equity = starting_capital
        max_drawdown = Decimal("0")
        trades: list[DailyTrade] = []

        for index in range(LONG_WINDOW, len(bars) - 1):
            signal = self._signal(bars, index, quantity > 0)
            fill_bar = bars[index + 1]
            if signal == "BUY" and quantity == 0:
                quantity = (cash / fill_bar.open).quantize(
                    Decimal("0.0001"), rounding=ROUND_DOWN
                )
                cash -= quantity * fill_bar.open
                entry_price = fill_bar.open
                entry_date = fill_bar.session
            elif (
                signal == "SELL"
                and quantity > 0
                and entry_price is not None
                and entry_date is not None
            ):
                cash += quantity * fill_bar.open
                pnl = (fill_bar.open - entry_price) * quantity
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
                        reason="signal_on_close_fill_next_open",
                    )
                )
                quantity = Decimal("0")
                entry_price = None
                entry_date = None
            equity = cash + quantity * bars[index].close
            peak_equity = max(peak_equity, equity)
            drawdown = equity / peak_equity - 1
            max_drawdown = min(max_drawdown, drawdown)

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
                )
            )
        return BacktestSummary(
            symbol=symbol,
            start_date=bars[0].session,
            end_date=bars[-1].session,
            bars=len(bars),
            total_return=last_equity / starting_capital - 1,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            trade_count=len(trades),
            open_position=quantity > 0,
            starting_capital=starting_capital,
            ending_equity=last_equity,
            trades=tuple(trades),
        )


    def _portfolio_summary(
        self, starting_capital: Decimal, backtests: list[BacktestSummary]
    ) -> PortfolioSummary:
        ending_equity = sum((item.ending_equity for item in backtests), Decimal("0"))
        closed_trades = [
            trade for item in backtests for trade in item.trades if trade.pnl is not None
        ]
        winners = [trade for trade in closed_trades if trade.pnl is not None and trade.pnl > 0]
        win_rate = (
            Decimal(len(winners)) / Decimal(len(closed_trades))
            if closed_trades
            else Decimal("0")
        )
        max_drawdown = min((item.max_drawdown for item in backtests), default=Decimal("0"))
        return PortfolioSummary(
            starting_capital=starting_capital,
            ending_equity=ending_equity,
            total_return=(
                ending_equity / starting_capital - 1
                if starting_capital > 0
                else Decimal("0")
            ),
            open_positions=sum(1 for item in backtests if item.open_position),
            closed_trades=len(closed_trades),
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            cash_policy="equal_symbol_sleeves_rebalanced_at_report_start",
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
        signal = self._signal(bars, index, open_position)
        latest = bars[index]
        short = self._average_close(bars, index, SHORT_WINDOW)
        long = self._average_close(bars, index, LONG_WINDOW)
        momentum = latest.close / bars[index - SHORT_WINDOW].close - 1
        confidence = min(Decimal("0.95"), max(Decimal("0.10"), abs(short / long - 1) * 10))
        risk_notional = starting_capital * Decimal("0.25")
        suggested_quantity = (risk_notional / latest.close).quantize(
            Decimal("0.0001"), rounding=ROUND_DOWN
        ) if signal == "BUY" else Decimal("0")
        suggested_notional = suggested_quantity * latest.close
        reasons = (
            f"close={latest.close.quantize(Decimal('0.0001'))}",
            f"sma20={short.quantize(Decimal('0.0001'))}",
            f"sma50={long.quantize(Decimal('0.0001'))}",
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
            stop_loss=latest.close * Decimal("0.97") if signal == "BUY" else None,
            take_profit=latest.close * Decimal("1.06") if signal == "BUY" else None,
            suggested_quantity=suggested_quantity,
            suggested_notional=suggested_notional,
            reasons=reasons,
        )

    def _signal(self, bars: list[ResearchBar], index: int, open_position: bool) -> str:
        latest = bars[index]
        short = self._average_close(bars, index, SHORT_WINDOW)
        long = self._average_close(bars, index, LONG_WINDOW)
        momentum = latest.close / bars[index - SHORT_WINDOW].close - 1
        if not open_position and latest.close > short > long and momentum > 0:
            return "BUY"
        if open_position and (latest.close < short or short < long):
            return "SELL"
        return "HOLD"

    @staticmethod
    def _average_close(bars: list[ResearchBar], index: int, window: int) -> Decimal:
        closes = [float(bar.close) for bar in bars[index - window + 1 : index + 1]]
        return Decimal(str(mean(closes)))

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
