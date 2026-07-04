from datetime import date, timedelta
from decimal import Decimal

from backend.app.application.daily_research import ResearchBar
from backend.app.application.strategy_lab import StrategyLabService

MONTE_CARLO_SIMULATIONS = 200


def fake_fetch(symbol: str, start: date, end: date) -> list[ResearchBar]:
    first = date(2021, 1, 1)
    bars: list[ResearchBar] = []
    for index in range(420):
        trend = Decimal(index) / Decimal("4")
        close = Decimal("100") + trend + (Decimal(index % 7) / Decimal("10"))
        bars.append(
            ResearchBar(
                session=first + timedelta(days=index),
                open=close - Decimal("0.25"),
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume=1_000_000 + index,
            )
        )
    return bars


def test_strategy_lab_report_contains_optimizer_and_export_intents() -> None:
    report = StrategyLabService(fetcher=fake_fetch).build_report(
        ("SPY", "QQQ"), horizon_years=1, capital=Decimal("10000"), end=date(2022, 3, 1)
    )

    assert report.horizon_years == 1
    assert report.leaderboard
    assert report.parameter_optimizer
    assert report.feature_importance
    assert report.correlation_heatmap
    assert report.regime_performance
    assert report.paper_export_intents
    assert report.monte_carlo[0].simulations == MONTE_CARLO_SIMULATIONS
