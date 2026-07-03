from http import HTTPStatus

import pytest

pytest.importorskip("fastapi", reason="FastAPI dependency is required for API tests")

from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_endpoint_returns_runtime_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "KOC3 Quant Platform"
    assert payload["market_data_provider"] == "yahoo"
    assert "timestamp_utc" in payload
