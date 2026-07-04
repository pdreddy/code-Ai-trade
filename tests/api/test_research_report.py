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
)
from backend.app.main import create_app  # noqa: E402

HTTP_OK = 200


def test_daily_research_endpoint_returns_candidates_and_daywise_trades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_report(self, symbols):  # type: ignore[no-untyped-def]
        assert symbols == ("SPY",)
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
                    trades=(trade,),
                ),
            ),
        )

    monkeypatch.setattr(
        "backend.app.application.daily_research.DailyResearchService.build_report",
        fake_report,
    )

    response = TestClient(create_app()).get("/api/v1/research/daily-report?symbols=SPY")

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["candidates"][0]["action"] == "BUY"
    assert payload["backtests"][0]["trades"][0]["pnl"] == "250.0000"
