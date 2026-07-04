from datetime import date, timedelta
from decimal import Decimal

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.application.daily_research import ResearchBar  # noqa: E402
from backend.app.main import create_app  # noqa: E402

HTTP_OK = 200
BAR_COUNT = 90


def test_daily_research_endpoint_returns_institutional_research_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(self, symbol, start, end):  # type: ignore[no-untyped-def]
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
                    volume=1_000_000 + index,
                )
            )
        return bars

    monkeypatch.setattr(
        "backend.app.application.daily_research.DailyResearchService._fetch_bars",
        fake_fetch,
    )

    response = TestClient(create_app()).get(
        "/api/v1/research/daily-report?symbols=SPY&capital=10000"
    )

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["candidates"][0]["action"] in {"BUY", "SELL", "HOLD"}
    assert payload["candidates"][0]["ai_score"] is not None
    assert payload["candidates"][0]["agent_scores"]
    assert payload["backtests"][0]["starting_capital"] == "10000.0000"
    assert payload["backtests"][0]["equity_curve"]
    assert payload["backtests"][0]["benchmark_comparisons"]
    assert payload["backtests"][0]["sharpe_ratio"] is not None
    assert payload["backtests"][0]["trades"][0]["trade_id"]
    assert payload["portfolio"]["starting_capital"] == "10000.0000"
    assert payload["portfolio"]["cash"] is not None
    assert payload["portfolio"]["equity_curve"]
    assert "options_watchlist" in payload
