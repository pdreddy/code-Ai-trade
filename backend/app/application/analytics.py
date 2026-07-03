"""Analytics services derived from real backtest, trade, and portfolio inputs."""

from dataclasses import dataclass
from decimal import Decimal

from backend.app.application.backtesting import BacktestResult, DrawdownPoint, EquityPoint
from backend.app.domain.entities import Portfolio, Trade


@dataclass(frozen=True, slots=True)
class ChartPoint:
    timestamp: str
    value: Decimal


@dataclass(frozen=True, slots=True)
class TradeAnalytics:
    trade_count: int
    closed_trade_count: int
    win_count: int
    loss_count: int
    success_rate: Decimal
    average_realized_pnl: Decimal
    total_realized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioAnalytics:
    equity: Decimal
    cash: Decimal
    invested_value: Decimal
    unrealized_pnl: Decimal
    position_count: int
    gross_exposure: Decimal


@dataclass(frozen=True, slots=True)
class BacktestAnalyticsReport:
    success_rate: Decimal
    equity_curve: tuple[ChartPoint, ...]
    drawdown_curve: tuple[ChartPoint, ...]
    trade_analytics: TradeAnalytics
    portfolio_analytics: PortfolioAnalytics | None


class AnalyticsService:
    """Build chart DTOs and summaries from persisted or caller-supplied real results."""

    def summarize_backtest(
        self, result: BacktestResult, portfolio: Portfolio | None = None
    ) -> BacktestAnalyticsReport:
        trade_analytics = self.trade_analytics(
            tuple(backtest_trade.trade for backtest_trade in result.trades)
        )
        return BacktestAnalyticsReport(
            success_rate=trade_analytics.success_rate,
            equity_curve=_equity_chart(result.equity_curve),
            drawdown_curve=_drawdown_chart(result.drawdown_curve),
            trade_analytics=trade_analytics,
            portfolio_analytics=self.portfolio_analytics(portfolio) if portfolio else None,
        )

    def trade_analytics(self, trades: tuple[Trade, ...]) -> TradeAnalytics:
        closed_pnls = tuple(
            trade.realized_pnl for trade in trades if trade.realized_pnl is not None
        )
        wins = tuple(pnl for pnl in closed_pnls if pnl > Decimal("0"))
        losses = tuple(pnl for pnl in closed_pnls if pnl < Decimal("0"))
        total = sum(closed_pnls, Decimal("0"))
        closed_count = len(closed_pnls)
        return TradeAnalytics(
            trade_count=len(trades),
            closed_trade_count=closed_count,
            win_count=len(wins),
            loss_count=len(losses),
            success_rate=Decimal(len(wins)) / Decimal(closed_count)
            if closed_count
            else Decimal("0"),
            average_realized_pnl=total / Decimal(closed_count) if closed_count else Decimal("0"),
            total_realized_pnl=total,
        )

    def portfolio_analytics(self, portfolio: Portfolio) -> PortfolioAnalytics:
        invested_value = sum(
            (position.market_value for position in portfolio.positions), Decimal("0")
        )
        unrealized_pnl = sum(
            (position.unrealized_pnl for position in portfolio.positions), Decimal("0")
        )
        return PortfolioAnalytics(
            equity=portfolio.equity,
            cash=portfolio.cash,
            invested_value=invested_value,
            unrealized_pnl=unrealized_pnl,
            position_count=len(portfolio.positions),
            gross_exposure=invested_value / portfolio.equity
            if portfolio.equity != Decimal("0")
            else Decimal("0"),
        )


def _equity_chart(points: tuple[EquityPoint, ...]) -> tuple[ChartPoint, ...]:
    return tuple(ChartPoint(point.timestamp.isoformat(), point.equity) for point in points)


def _drawdown_chart(points: tuple[DrawdownPoint, ...]) -> tuple[ChartPoint, ...]:
    return tuple(ChartPoint(point.timestamp.isoformat(), point.drawdown) for point in points)
