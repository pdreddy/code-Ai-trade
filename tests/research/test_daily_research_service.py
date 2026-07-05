from datetime import date, timedelta
from decimal import Decimal

from backend.app.application.daily_research import DailyResearchService, ResearchBar

BAR_COUNT = 80


class DeterministicDailyResearchService(DailyResearchService):
    def _fetch_bars(self, symbol, start, end):  # type: ignore[no-untyped-def]
        first = date(2021, 1, 1)
        bars: list[ResearchBar] = []
        for index in range(BAR_COUNT):
            close = Decimal("100") + Decimal(index)
            bars.append(
                ResearchBar(
                    session=first + timedelta(days=index),
                    open=close - Decimal("0.5"),
                    high=close + Decimal("1"),
                    low=close - Decimal("1"),
                    close=close,
                    volume=1_000_000,
                )
            )
        return bars


def test_daily_research_report_contains_next_day_candidates_and_backtests() -> None:
    report = DeterministicDailyResearchService().build_report(("spy",), end=date(2021, 3, 31))

    assert report.candidates[0].symbol == "SPY"
    assert report.candidates[0].planned_execution == "next_session_open_paper_candidate"
    assert report.candidates[0].action in {"BUY", "SELL", "HOLD"}
    assert report.backtests[0].symbol == "SPY"
    assert report.backtests[0].bars == BAR_COUNT
    assert report.backtests[0].trade_count >= 1
    assert report.backtests[0].starting_capital == Decimal("10000")
    assert report.backtests[0].ending_equity > Decimal("10000")
    assert report.zero_dte_option_intents[0].symbol == "SPY"
    assert report.zero_dte_option_intents[0].option_type in {"CALL", "PUT"}
    assert report.zero_dte_option_intents[0].status == "REQUIRES_OPTIONS_PROVIDER_NO_EXECUTION"


class LowMomentumDailyResearchService(DailyResearchService):
    def _fetch_bars(self, symbol, start, end):  # type: ignore[no-untyped-def]
        first = date(2021, 1, 1)
        bars: list[ResearchBar] = []
        for index in range(BAR_COUNT):
            close = Decimal("100") + Decimal(index) / Decimal("100")
            bars.append(
                ResearchBar(
                    session=first + timedelta(days=index),
                    open=close,
                    high=close + Decimal("0.5"),
                    low=close - Decimal("0.5"),
                    close=close,
                    volume=1_000_000,
                )
            )
        return bars


def test_daily_research_strategy_rejects_low_momentum_churn() -> None:
    report = LowMomentumDailyResearchService().build_report(("spy",), end=date(2021, 3, 31))

    assert report.candidates[0].action == "HOLD"
    assert report.backtests[0].trade_count == 0
