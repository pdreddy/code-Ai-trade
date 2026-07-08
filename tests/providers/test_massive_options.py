from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from backend.app.domain.options import OptionType
from backend.app.infrastructure.providers.massive_options import (
    DEFAULT_TIMEOUT_SECONDS,
    MassiveOptionsProvider,
)

EXPECTED_VOLUME = 868
EXPECTED_OPEN_INTEREST = 1543


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_massive_options_provider_maps_snapshot_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    expiration = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
    payload = f"""
    {{
      "status": "OK",
      "results": [
        {{
          "day": {{"volume": 868}},
          "details": {{
            "contract_type": "call",
            "expiration_date": "{expiration}",
            "strike_price": 150,
            "ticker": "O:AAPL260710C00150000"
          }},
          "implied_volatility": 0.42,
          "last_quote": {{"bid": 1.2, "ask": 1.3}},
          "last_trade": {{"price": 1.25}},
          "open_interest": 1543,
          "underlying_asset": {{"price": 151, "ticker": "AAPL"}}
        }}
      ]
    }}
    """.encode()
    seen_urls: list[str] = []

    def fake_urlopen(request: Any, timeout: int) -> _Response:
        seen_urls.append(request.full_url)
        assert timeout == DEFAULT_TIMEOUT_SECONDS
        return _Response(payload)

    monkeypatch.setattr(
        "backend.app.infrastructure.providers.massive_options.urlopen", fake_urlopen
    )

    chain = MassiveOptionsProvider(api_key="secret").fetch_option_chain("aapl", max_expiries=1)

    assert chain.symbol == "AAPL"
    assert chain.underlying_price == Decimal("151")
    assert len(chain.contracts) == 1
    contract = chain.contracts[0]
    assert contract.contract_symbol == "O:AAPL260710C00150000"
    assert contract.option_type is OptionType.CALL
    assert contract.strike == Decimal("150")
    assert contract.bid == Decimal("1.2")
    assert contract.ask == Decimal("1.3")
    assert contract.last_price == Decimal("1.25")
    assert contract.volume == EXPECTED_VOLUME
    assert contract.open_interest == EXPECTED_OPEN_INTEREST
    assert contract.implied_volatility == Decimal("0.42")
    assert contract.in_the_money is True
    assert "apiKey=secret" in seen_urls[0]
