import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from backend.app.domain.enums import CorporateActionType
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import HistoricalMarketDataRequest
from backend.app.infrastructure.providers import yahoo as yahoo_module
from backend.app.infrastructure.providers.yahoo import (
    YahooFinanceProvider,
    YahooFinanceProviderError,
    _extract_result,
    _parse_bars,
    _parse_corporate_actions,
)

EXPECTED_COMPLETE_BAR_COUNT = 2
EXPECTED_SECOND_BAR_VOLUME = 2_345_678


def _request() -> HistoricalMarketDataRequest:
    return HistoricalMarketDataRequest(
        instrument_id=uuid4(),
        symbol="SPY",
        start=date(2024, 1, 2),
        end=date(2024, 1, 5),
    )


def _chart_result() -> dict[str, object]:
    return {
        "timestamp": [1704191400, 1704277800, 1704364200],
        "indicators": {
            "quote": [
                {
                    "open": [472.16, 470.43, None],
                    "high": [473.67, 471.19, None],
                    "low": [470.49, 468.17, None],
                    "close": [472.65, 468.79, None],
                    "volume": [1234567, 2345678, None],
                }
            ],
            "adjclose": [{"adjclose": [468.20, 464.38, None]}],
        },
        "events": {
            "dividends": {
                "1704191400": {"amount": 1.23, "date": 1704191400},
            },
            "splits": {
                "1704277800": {
                    "numerator": 2,
                    "denominator": 1,
                    "date": 1704277800,
                }
            },
        },
    }


def test_historical_market_data_request_validates_symbol_and_dates() -> None:
    with pytest.raises(DomainValidationError, match="symbol"):
        HistoricalMarketDataRequest(
            instrument_id=uuid4(),
            symbol="SPY/USD",
            start=date(2024, 1, 2),
            end=date(2024, 1, 5),
        )

    with pytest.raises(DomainValidationError, match="end date"):
        HistoricalMarketDataRequest(
            instrument_id=uuid4(),
            symbol="SPY",
            start=date(2024, 1, 5),
            end=date(2024, 1, 5),
        )


def test_yahoo_chart_parser_normalizes_complete_bars_and_skips_incomplete_rows() -> None:
    request = _request()

    bars = _parse_bars(_chart_result(), request)

    assert len(bars) == EXPECTED_COMPLETE_BAR_COUNT
    assert bars[0].instrument_id == request.instrument_id
    assert bars[0].open.value == Decimal("472.16")
    assert bars[0].adjusted_close is not None
    assert bars[0].adjusted_close.value == Decimal("468.2")
    assert bars[1].volume == EXPECTED_SECOND_BAR_VOLUME


def test_yahoo_chart_parser_normalizes_dividends_and_splits() -> None:
    request = _request()

    actions = _parse_corporate_actions(_chart_result(), request)

    assert [action.action_type for action in actions] == [
        CorporateActionType.DIVIDEND,
        CorporateActionType.SPLIT,
    ]
    assert actions[0].value == Decimal("1.23")
    assert actions[1].value == Decimal("2")
    assert {action.source for action in actions} == {"yahoo.chart.v8"}


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_yahoo_provider_sends_browser_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        captured["request"] = request
        payload = {"chart": {"error": None, "result": [_chart_result()]}}
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(yahoo_module, "urlopen", fake_urlopen)

    data = YahooFinanceProvider().fetch_daily_history(_request())

    user_agent = captured["request"].get_header("User-agent")
    assert user_agent is not None
    assert "Mozilla" in user_agent
    assert len(data.bars) == EXPECTED_COMPLETE_BAR_COUNT


def test_yahoo_result_extraction_fails_on_provider_errors() -> None:
    payload = {"chart": {"result": None, "error": {"code": "Not Found"}}}

    with pytest.raises(YahooFinanceProviderError, match="returned an error"):
        _extract_result(payload, "SPY")
