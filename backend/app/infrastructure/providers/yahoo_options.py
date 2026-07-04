"""Yahoo Finance options-chain adapter.

Uses Yahoo's options endpoint to retrieve near-term expiries and converts each
call/put into a domain ``OptionContract``. The base response carries the nearest
expiry plus the full list of expiration dates; additional near-term expiries are
fetched by epoch so 0DTE and weekly contracts are all available. No persistence
and no trading logic live here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.domain.options import OptionChain, OptionContract, OptionType
from backend.app.infrastructure.providers.yahoo import (
    DEFAULT_TIMEOUT_SECONDS,
    REQUEST_HEADERS,
    YahooFinanceProviderError,
)

YAHOO_OPTIONS_URL = "https://query1.finance.yahoo.com/v7/finance/options/{symbol}"


class YahooOptionsProvider:
    """Yahoo Finance implementation of the options-provider contract."""

    provider_name = "yahoo"

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        upper = symbol.upper()
        base = self._get_options_payload(upper, expiry_epoch=None)
        result = _extract_result(base, upper)
        underlying = _underlying_price(result, upper)
        expirations = _expiration_epochs(result)[: max(1, max_expiries)]

        contracts: list[OptionContract] = []
        # The base call already carries the nearest expiry's chain; reuse it and only
        # fetch the additional near-term expiries so 0DTE and weeklies are covered.
        seen_epochs: set[int] = set()
        first_epoch = _first_option_epoch(result)
        if first_epoch is not None:
            seen_epochs.add(first_epoch)
            contracts.extend(_parse_options_block(result, upper))
        for epoch in expirations:
            if epoch in seen_epochs:
                continue
            payload = self._get_options_payload(upper, expiry_epoch=epoch)
            expiry_result = _extract_result(payload, upper)
            contracts.extend(_parse_options_block(expiry_result, upper))
            seen_epochs.add(epoch)

        return OptionChain(
            symbol=upper,
            underlying_price=underlying,
            retrieved_at_utc_iso=datetime.now(UTC).isoformat(),
            contracts=tuple(contracts),
        )

    def _get_options_payload(
        self, symbol: str, expiry_epoch: int | None
    ) -> Mapping[str, Any]:
        query = urlencode({"date": expiry_epoch}) if expiry_epoch is not None else ""
        url = YAHOO_OPTIONS_URL.format(symbol=symbol)
        if query:
            url = f"{url}?{query}"
        http_request = Request(url, headers=REQUEST_HEADERS)  # noqa: S310
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:  # noqa: S310
                return cast(Mapping[str, Any], json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance rejected options for {symbol} with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance options request failed for {symbol}: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance returned invalid options JSON for {symbol}"
            ) from exc


def _extract_result(payload: Mapping[str, Any], symbol: str) -> Mapping[str, Any]:
    chain = payload.get("optionChain")
    if not isinstance(chain, Mapping):
        raise YahooFinanceProviderError(f"Yahoo options response missing chain for {symbol}")
    error = chain.get("error")
    if error is not None:
        raise YahooFinanceProviderError(f"Yahoo options returned an error for {symbol}: {error}")
    results = chain.get("result")
    if not isinstance(results, list) or not results:
        raise YahooFinanceProviderError(f"Yahoo options returned no result for {symbol}")
    result = results[0]
    if not isinstance(result, Mapping):
        raise YahooFinanceProviderError(f"Yahoo options result malformed for {symbol}")
    return result


def _underlying_price(result: Mapping[str, Any], symbol: str) -> Decimal:
    quote = result.get("quote")
    if isinstance(quote, Mapping):
        price = _decimal(quote.get("regularMarketPrice"))
        if price is not None and price > Decimal("0"):
            return price
    raise YahooFinanceProviderError(f"Yahoo options missing underlying price for {symbol}")


def _expiration_epochs(result: Mapping[str, Any]) -> list[int]:
    dates = result.get("expirationDates")
    if not isinstance(dates, list):
        return []
    return [int(value) for value in dates if isinstance(value, int | float)]


def _first_option_epoch(result: Mapping[str, Any]) -> int | None:
    options = result.get("options")
    if not isinstance(options, list) or not options:
        return None
    block = options[0]
    if not isinstance(block, Mapping):
        return None
    epoch = block.get("expirationDate")
    return int(epoch) if isinstance(epoch, int | float) else None


def _parse_options_block(result: Mapping[str, Any], symbol: str) -> list[OptionContract]:
    options = result.get("options")
    if not isinstance(options, list) or not options:
        return []
    contracts: list[OptionContract] = []
    today = datetime.now(UTC).date()
    for block in options:
        if not isinstance(block, Mapping):
            continue
        expiry = _epoch_to_date(block.get("expirationDate"))
        if expiry is None:
            continue
        dte = max((expiry - today).days, 0)
        contracts.extend(_parse_side(block.get("calls"), OptionType.CALL, expiry, dte))
        contracts.extend(_parse_side(block.get("puts"), OptionType.PUT, expiry, dte))
    return contracts


def _parse_side(
    rows: Any, option_type: OptionType, expiry: date, dte: int
) -> list[OptionContract]:
    if not isinstance(rows, Sequence):
        return []
    contracts: list[OptionContract] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        strike = _decimal(row.get("strike"))
        if strike is None or strike <= Decimal("0"):
            continue
        contracts.append(
            OptionContract(
                contract_symbol=str(row.get("contractSymbol", "")),
                option_type=option_type,
                strike=strike,
                expiration=expiry,
                days_to_expiry=dte,
                last_price=_decimal(row.get("lastPrice")),
                bid=_decimal(row.get("bid")),
                ask=_decimal(row.get("ask")),
                volume=_int(row.get("volume")),
                open_interest=_int(row.get("openInterest")),
                implied_volatility=_decimal(row.get("impliedVolatility")),
                in_the_money=bool(row.get("inTheMoney", False)),
            )
        )
    return contracts


def _epoch_to_date(value: Any) -> date | None:
    if not isinstance(value, int | float):
        return None
    return datetime.fromtimestamp(int(value), tz=UTC).date()


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
