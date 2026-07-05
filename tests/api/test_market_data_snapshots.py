from datetime import date
from decimal import Decimal

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.application.market_snapshot import MarketSnapshot  # noqa: E402
from backend.app.main import create_app  # noqa: E402

HTTP_OK = 200
SPY_BAR_COUNT = 1258


def test_five_year_snapshot_endpoint_returns_provider_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_snapshots(self, symbols):  # type: ignore[no-untyped-def]
        assert symbols == ("SPY",)
        return (
            MarketSnapshot(
                symbol="SPY",
                start_date=date(2021, 7, 6),
                end_date=date(2026, 7, 2),
                bars=SPY_BAR_COUNT,
                last_close=Decimal("625.34"),
                total_return=Decimal("0.8123"),
                cagr=Decimal("0.1267"),
                max_drawdown=Decimal("-0.2411"),
                realized_volatility=Decimal("0.1888"),
            ),
        )

    monkeypatch.setattr(
        "backend.app.application.market_snapshot.MarketSnapshotService.five_year_snapshots",
        fake_snapshots,
    )

    response = TestClient(create_app()).get("/api/v1/market-data/snapshots/five-year?symbols=SPY")

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["snapshots"][0]["symbol"] == "SPY"
    assert payload["snapshots"][0]["bars"] == SPY_BAR_COUNT
    assert payload["snapshots"][0]["total_return"] == "0.8123"
