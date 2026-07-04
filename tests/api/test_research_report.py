from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.application.daily_research import (  # noqa: E402
    BacktestSummary,
    DailyResearchReport,
    DailyTrade,
    NextDayCandidate,
    OptionsWatchCandidate,
    PortfolioSummary,
)
from backend.app.main import create_app  # noqa: E402

HTTP_OK = 200


def test_daily_research_endpoint_returns_candidates_and_daywise_trades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_report(self, symbols, *, starting_capital):  # type: ignore[no-untyped-def]
        assert symbols == ("SPY",)
        assert starting_capital == Decimal("10000")
        trade = DailyTrade(
            symbol="SPY",
            entry_date=date(2026, 1, 2),
            entry_price=Decimal("500"),
            exit_date=date(2026, 1, 10),
            exit_price=Decimal("525"),
            quantity=Decimal("10"),
            pnl=Decimal("250"),
            return_pct=Decimal("0.05"),
            reason="signal_on_close_fill_next_open",
        )
        return DailyResearchReport(
            generated_at=datetime(2026, 7, 4, tzinfo=UTC),
            candidates=(
                NextDayCandidate(
                    symbol="SPY",
                    signal_date=date(2026, 7, 2),
                    action="BUY",
                    confidence=Decimal("0.75"),
                    planned_execution="next_session_open_paper_candidate",
                    last_close=Decimal("744.78"),
                    stop_loss=Decimal("722.4366"),
                    take_profit=Decimal("789.4668"),
                    suggested_quantity=Decimal("1.6783"),
                    suggested_notional=Decimal("1249.9805"),
                    reasons=("signal_on_close_fill_next_open",),
                ),
            ),
            backtests=(
                BacktestSummary(
                    symbol="SPY",
                    start_date=date(2021, 7, 6),
                    end_date=date(2026, 7, 2),
                    bars=1254,
                    total_return=Decimal("0.25"),
                    win_rate=Decimal("1"),
                    max_drawdown=Decimal("-0.10"),
                    trade_count=1,
                    open_position=False,
                    starting_capital=Decimal("10000"),
                    ending_equity=Decimal("10500"),
                    trades=(trade,),
                ),
            ),
            portfolio=PortfolioSummary(
                starting_capital=Decimal("10000"),
                ending_equity=Decimal("10500"),
                total_return=Decimal("0.05"),
                open_positions=0,
                closed_trades=1,
                win_rate=Decimal("1"),
                max_drawdown=Decimal("-0.10"),
                cash_policy="equal_symbol_sleeves_rebalanced_at_report_start",
            ),
            options_watchlist=(
                OptionsWatchCandidate(
                    symbol="SPY",
                    signal_date=date(2026, 7, 2),
                    underlying_action="BUY",
                    watch_type="CALL_WATCH",
                    urgency=Decimal("0.80"),
                    underlying_last_close=Decimal("744.78"),
                    suggested_underlying_notional=Decimal("1249.9805"),
                    rationale=("Options-chain execution is not enabled",),
                ),
            ),
        )

    monkeypatch.setattr(
        "backend.app.application.daily_research.DailyResearchService.build_report",
        fake_report,
    )

    response = TestClient(create_app()).get(
        "/api/v1/research/daily-report?symbols=SPY&capital=10000"
    )

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["candidates"][0]["action"] == "BUY"
    assert payload["candidates"][0]["suggested_quantity"] == "1.6783"
    assert payload["backtests"][0]["starting_capital"] == "10000.0000"
    assert payload["backtests"][0]["ending_equity"] == "10500.0000"
    assert payload["portfolio"]["starting_capital"] == "10000.0000"
    assert payload["options_watchlist"][0]["watch_type"] == "CALL_WATCH"
    assert payload["backtests"][0]["trades"][0]["pnl"] == "250.0000"
