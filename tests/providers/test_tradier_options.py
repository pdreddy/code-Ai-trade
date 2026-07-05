from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from backend.app.infrastructure.providers.tradier_options import (
    TradierOptionsProvider,
    TradierProviderError,
    _as_list,
    _parse_contract,
)

TODAY = date.today()
DAYS_TO_EXPIRY = 5
EXPIRATION = TODAY + timedelta(days=DAYS_TO_EXPIRY)
TWO_CONTRACTS = 2


def test_tradier_provider_requires_a_token() -> None:
    with pytest.raises(TradierProviderError):
        TradierOptionsProvider(api_token="")


def test_as_list_normalizes_tradier_singular_vs_plural_quirk() -> None:
    # Tradier returns a bare dict when there's exactly one item, and a list
    # when there are several — a well-known quirk of this API.
    assert _as_list(None) == []
    assert _as_list({"a": 1}) == [{"a": 1}]
    assert _as_list([{"a": 1}, {"a": 2}]) == [{"a": 1}, {"a": 2}]


def test_parse_contract_maps_tradier_fields_and_computes_itm() -> None:
    row = {
        "symbol": "AAPL260710C00150000",
        "option_type": "call",
        "strike": 150,
        "last": 2.35,
        "bid": 2.30,
        "ask": 2.40,
        "volume": 500,
        "open_interest": 1200,
        "greeks": {"mid_iv": 0.28},
    }

    contract = _parse_contract(row, EXPIRATION, dte=5, underlying_price=Decimal("155"))

    assert contract is not None
    assert contract.contract_symbol == "AAPL260710C00150000"
    assert contract.strike == Decimal("150")
    assert contract.last_price == Decimal("2.35")
    assert contract.implied_volatility == Decimal("0.28")
    assert contract.in_the_money is True  # call strike below spot


def test_parse_contract_rejects_unknown_option_type() -> None:
    row = {"symbol": "X", "option_type": "straddle", "strike": 100}

    assert _parse_contract(row, EXPIRATION, dte=5, underlying_price=Decimal("100")) is None


def test_parse_contract_rejects_non_positive_strike() -> None:
    row = {"symbol": "X", "option_type": "put", "strike": 0}

    assert _parse_contract(row, EXPIRATION, dte=5, underlying_price=Decimal("100")) is None


class _StubbedProvider(TradierOptionsProvider):
    """Overrides the one network-touching method with canned payloads."""

    def __init__(self, payloads: Mapping[str, Mapping[str, Any]]) -> None:
        super().__init__(api_token="test-token")
        self._payloads = payloads

    def _get(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        return self._payloads[path]


def test_fetch_option_chain_orchestrates_quote_expirations_and_chain() -> None:
    provider = _StubbedProvider(
        {
            "/markets/quotes": {"quotes": {"quote": {"symbol": "AAPL", "last": 200.5}}},
            "/markets/options/expirations": {
                "expirations": {"date": [EXPIRATION.isoformat()]}
            },
            "/markets/options/chains": {
                "options": {
                    "option": [
                        {
                            "symbol": "AAPL_TEST_CALL",
                            "option_type": "call",
                            "strike": 195,
                            "last": 8.0,
                            "bid": 7.9,
                            "ask": 8.1,
                            "volume": 1000,
                            "open_interest": 500,
                            "greeks": {"mid_iv": 0.30},
                        },
                        {
                            "symbol": "AAPL_TEST_PUT",
                            "option_type": "put",
                            "strike": 205,
                            "last": 6.0,
                            "bid": 5.9,
                            "ask": 6.1,
                            "volume": 700,
                            "open_interest": 300,
                            "greeks": {"mid_iv": 0.32},
                        },
                    ]
                }
            },
        }
    )

    chain = provider.fetch_option_chain("aapl", max_expiries=3)

    assert chain.symbol == "AAPL"
    assert chain.underlying_price == Decimal("200.5")
    assert len(chain.contracts) == TWO_CONTRACTS
    call = next(c for c in chain.contracts if c.option_type.value == "call")
    put = next(c for c in chain.contracts if c.option_type.value == "put")
    assert call.in_the_money is True  # 195 strike < 200.5 spot -> call ITM
    assert put.in_the_money is True  # 205 strike > 200.5 spot -> put ITM
    assert call.days_to_expiry == DAYS_TO_EXPIRY


def test_fetch_option_chain_raises_when_quote_missing() -> None:
    provider = _StubbedProvider({"/markets/quotes": {"quotes": {}}})

    with pytest.raises(TradierProviderError):
        provider.fetch_option_chain("AAPL")
