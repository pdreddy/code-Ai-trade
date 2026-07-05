from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from uuid import uuid4

import pytest

pytest.importorskip("fastapi", reason="FastAPI dependency is required for API tests")

from fastapi.testclient import TestClient

from backend.app.main import create_app

TRADE_COUNT = 2


def test_capability_endpoints_report_ready_application_services() -> None:
    client = TestClient(create_app())

    capability_paths = (
        "/api/v1/backtests/capabilities",
        "/api/v1/paper-trading/capabilities",
        "/api/v1/risk/capabilities",
    )
    for path in capability_paths:
        response = client.get(path)
        assert response.status_code == HTTPStatus.OK
        assert response.json()["status"] == "application_service_ready"


def test_trade_analytics_endpoint_uses_supplied_trade_records() -> None:
    client = TestClient(create_app())
    instrument_id = str(uuid4())
    entry_order_id = str(uuid4())
    now = datetime(2026, 1, 1, tzinfo=UTC)

    response = client.post(
        "/api/v1/analytics/trades/summary",
        json={
            "trades": [
                {
                    "id": str(uuid4()),
                    "instrument_id": instrument_id,
                    "entry_order_id": entry_order_id,
                    "exit_order_id": str(uuid4()),
                    "entry_at": now.isoformat(),
                    "entry_price": "100",
                    "quantity": "10",
                    "exit_at": (now + timedelta(days=1)).isoformat(),
                    "exit_price": "110",
                    "realized_pnl": "100",
                    "reason": "real closed trade",
                },
                {
                    "id": str(uuid4()),
                    "instrument_id": instrument_id,
                    "entry_order_id": str(uuid4()),
                    "exit_order_id": str(uuid4()),
                    "entry_at": now.isoformat(),
                    "entry_price": "100",
                    "quantity": "10",
                    "exit_at": (now + timedelta(days=1)).isoformat(),
                    "exit_price": "95",
                    "realized_pnl": "-50",
                    "reason": "real losing trade",
                },
            ]
        },
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["trade_count"] == TRADE_COUNT
    assert payload["win_count"] == 1
    assert payload["loss_count"] == 1
    assert payload["success_rate"] == "0.5"
    assert payload["total_realized_pnl"] == "50"


def test_platform_readiness_gaps_identify_blockers() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/platform/readiness-gaps")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    areas = {item["area"] for item in payload}
    assert "0DTE options execution" in areas
    assert "Persistent paper-trading ledger" in areas
    assert any(item["severity"] == "critical" for item in payload)
