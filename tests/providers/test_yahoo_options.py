from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError

import pytest

from backend.app.infrastructure.providers.yahoo_options import (
    CRUMB_URL,
    YAHOO_OPTIONS_URL,
    YahooFinanceProviderError,
    YahooOptionsProvider,
)

EXPECTED_CRUMB_FETCH_COUNT = 2


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _chain_payload(symbol: str, expiration_epoch: int) -> bytes:
    payload = {
        "optionChain": {
            "error": None,
            "result": [
                {
                    "quote": {"regularMarketPrice": 200.5},
                    "expirationDates": [expiration_epoch],
                    "options": [
                        {
                            "expirationDate": expiration_epoch,
                            "calls": [
                                {
                                    "contractSymbol": f"{symbol}TESTCALL",
                                    "strike": 195,
                                    "lastPrice": 8.0,
                                    "bid": 7.9,
                                    "ask": 8.1,
                                    "volume": 1000,
                                    "openInterest": 500,
                                    "impliedVolatility": 0.3,
                                    "inTheMoney": True,
                                }
                            ],
                            "puts": [],
                        }
                    ],
                }
            ],
        }
    }
    return json.dumps(payload).encode("utf-8")


class _FakeOpener:
    """Records requests and serves canned responses; can simulate one 401."""

    def __init__(self, *, unauthorized_once: bool = False) -> None:
        self.requests: list[str] = []
        self._unauthorized_once = unauthorized_once
        self._served_options_request = False

    def open(self, request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        self.requests.append(url)

        if url == "https://fc.yahoo.com":
            return _FakeResponse(b"")
        if url == CRUMB_URL:
            return _FakeResponse(b"test-crumb")
        if url.startswith(YAHOO_OPTIONS_URL.format(symbol="NFLX")):
            if self._unauthorized_once and not self._served_options_request:
                self._served_options_request = True
                raise HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)  # type: ignore[arg-type]
            expiration_epoch = int(datetime.now(UTC).timestamp())
            return _FakeResponse(_chain_payload("NFLX", expiration_epoch))
        raise AssertionError(f"unexpected request: {url}")


def test_fetch_option_chain_includes_crumb_after_bootstrapping_cookie() -> None:
    opener = _FakeOpener()
    provider = YahooOptionsProvider(opener=opener)  # type: ignore[arg-type]

    chain = provider.fetch_option_chain("nflx", max_expiries=1)

    assert chain.symbol == "NFLX"
    assert chain.underlying_price == Decimal("200.5")
    assert len(chain.contracts) == 1
    # Cookie bootstrap, then crumb fetch, then the options request itself.
    assert opener.requests[0] == "https://fc.yahoo.com"
    assert opener.requests[1] == CRUMB_URL
    assert "crumb=test-crumb" in opener.requests[2]


def test_fetch_option_chain_refreshes_crumb_once_after_401() -> None:
    opener = _FakeOpener(unauthorized_once=True)
    provider = YahooOptionsProvider(opener=opener)  # type: ignore[arg-type]

    chain = provider.fetch_option_chain("NFLX", max_expiries=1)

    assert chain.symbol == "NFLX"
    # The crumb endpoint is hit twice: once up front, once after the 401.
    assert opener.requests.count(CRUMB_URL) == EXPECTED_CRUMB_FETCH_COUNT


class _AlwaysUnauthorizedOpener:
    def open(self, request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if url in ("https://fc.yahoo.com", CRUMB_URL):
            return _FakeResponse(b"test-crumb")
        raise HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)  # type: ignore[arg-type]


def test_fetch_option_chain_raises_after_persistent_401() -> None:
    provider = YahooOptionsProvider(opener=_AlwaysUnauthorizedOpener())  # type: ignore[arg-type]

    with pytest.raises(YahooFinanceProviderError, match="401"):
        provider.fetch_option_chain("NFLX")
