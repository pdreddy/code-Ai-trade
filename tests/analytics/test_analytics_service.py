from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from backend.app.application.analytics import AnalyticsService
from backend.app.application.backtesting import BacktestRequest, EventDrivenBacktester
from backend.app.domain.entities import (
    BacktestRun,
    Bar,
    MasterDecision,
    Portfolio,
    PortfolioPosition,
)
from backend.app.domain.enums import SignalAction
from backend.app.domain.value_objects import Confidence, Price, Quantity, RiskFraction


def _bar(instrument_id: UUID, day: int, open_price: str, close_price: str) -> Bar:
    open_value = Decimal(open_price)
    close_value = Decimal(close_price)
    return Bar(
        instrument_id=instrument_id,
        timestamp=datetime(2026, 1, day, 14, 30, tzinfo=UTC),
        open=Price(open_value),
        high=Price(max(open_value, close_value) + Decimal("1")),
        low=Price(min(open_value, close_value) - Decimal("1")),
        close=Price(close_value),
        volume=1_000_000,
    )


def _decision(instrument_id: UUID, action: SignalAction, signal_at: datetime) -> MasterDecision:
    return MasterDecision(
        id=uuid4(),
        instrument_id=instrument_id,
        action=action,
        confidence=Confidence(Decimal("0.80")),
        risk_score=RiskFraction(Decimal("0.20")),
        stop_loss=None,
        take_profit=None,
        expected_r_multiple=Decimal("0"),
        explanation=f"{action.value} decision",
        agent_signal_ids=(uuid4(),),
        generated_at=signal_at + timedelta(minutes=1),
        signal_bar_timestamp=signal_at,
    )


def test_analytics_report_uses_real_backtest_and_portfolio_inputs() -> None:
    instrument_id = uuid4()
    bars = (
        _bar(instrument_id, 1, "100", "101"),
        _bar(instrument_id, 2, "102", "103"),
        _bar(instrument_id, 3, "104", "105"),
        _bar(instrument_id, 4, "106", "107"),
    )
    run = BacktestRun(
        id=uuid4(),
        strategy_name="analytics-fixture",
        instrument_id=instrument_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 6),
        initial_capital=Decimal("10000"),
        commission=Decimal("1"),
        slippage_bps=Decimal("0"),
        benchmark_symbol="SPY",
    )
    result = EventDrivenBacktester().run(
        BacktestRequest(
            run=run,
            bars=bars,
            decisions=(
                _decision(instrument_id, SignalAction.BUY, bars[0].timestamp),
                _decision(instrument_id, SignalAction.SELL, bars[2].timestamp),
            ),
        )
    )
    portfolio = Portfolio(
        id=uuid4(),
        name="paper",
        base_currency="USD",
        cash=Decimal("5000"),
        positions=(
            PortfolioPosition(
                instrument_id=instrument_id,
                quantity=Quantity(Decimal("10")),
                average_cost=Price(Decimal("100")),
                market_price=Price(Decimal("110")),
                as_of=bars[-1].timestamp,
            ),
        ),
        as_of=bars[-1].timestamp,
    )

    report = AnalyticsService().summarize_backtest(result, portfolio)

    assert report.success_rate == Decimal("1")
    assert len(report.equity_curve) == len(bars)
    assert len(report.drawdown_curve) == len(bars)
    assert report.trade_analytics.trade_count == 1
    assert report.trade_analytics.total_realized_pnl > Decimal("0")
    assert report.portfolio_analytics is not None
    assert report.portfolio_analytics.unrealized_pnl == Decimal("100")
