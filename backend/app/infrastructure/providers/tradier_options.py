"""Tradier options-chain adapter (sandbox or production).

Yahoo's undocumented options endpoint blocks server/datacenter IPs far more
aggressively than its chart endpoint, so it can be unreliable in production
even when regular price history works fine. Tradier is a real brokerage
market-data API with a free developer sandbox account, offered here as a
provider-agnostic alternative behind the same ``OptionsProvider`` contract:
one call for the quote (underlying price), one for the expiration calendar,
and one chain call per expiry. No persistence and no trading logic live here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.domain.options import OptionChain, OptionContract, OptionType

DEFAULT_TIMEOUT_SECONDS = 20
TRADIER_SANDBOX_BASE_URL = "https://sandbox.tradier.com/v1"
TRADIER_PRODUCTION_BASE_URL = "https://api.tradier.com/v1"


class TradierProviderError(RuntimeError):
    """Raised when Tradier returns invalid, incomplete, or unavailable data."""


class TradierOptionsProvider:
    """Tradier brokerage market-data implementation of the options-provider contract."""

    provider_name = "tradier"

    def __init__(
        self,
        api_token: str,
        base_url: str = TRADIER_SANDBOX_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_token:
            raise TradierProviderError("Tradier API token is required")
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        upper = symbol.upper()
        underlying = self._fetch_quote(upper)
        expirations = self._fetch_expirations(upper)[: max(1, max_expiries)]

        contracts: list[OptionContract] = []
        for expiration in expirations:
            contracts.extend(self._fetch_chain(upper, expiration, underlying))

        return OptionChain(
            symbol=upper,
            underlying_price=underlying,
            retrieved_at_utc_iso=datetime.now(UTC).isoformat(),
            contracts=tuple(contracts),
        )

    def _get(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        url = f"{self._base_url}{path}?{urlencode(params)}"
        request = Request(  # noqa: S310
            url,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                return cast(Mapping[str, Any], json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            symbol = params.get("symbol", "")
            raise TradierProviderError(
                f"Tradier rejected {path} for {symbol} with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise TradierProviderError(f"Tradier request failed for {path}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise TradierProviderError(f"Tradier returned invalid JSON for {path}") from exc

    def _fetch_quote(self, symbol: str) -> Decimal:
        payload = self._get("/markets/quotes", {"symbols": symbol})
        quotes = payload.get("quotes")
        if not isinstance(quotes, Mapping):
            raise TradierProviderError(f"Tradier quote response malformed for {symbol}")
        quote = _as_list(quotes.get("quote"))
        if not quote or not isinstance(quote[0], Mapping):
            raise TradierProviderError(f"Tradier returned no quote for {symbol}")
        price = _decimal(quote[0].get("last"))
        if price is None or price <= Decimal("0"):
            raise TradierProviderError(f"Tradier quote missing a usable last price for {symbol}")
        return price

    def _fetch_expirations(self, symbol: str) -> list[date]:
        payload = self._get(
            "/markets/options/expirations", {"symbol": symbol, "includeAllRoots": "true"}
        )
        expirations = payload.get("expirations")
        if not isinstance(expirations, Mapping):
            return []
        parsed: list[date] = []
        for value in _as_list(expirations.get("date")):
            if isinstance(value, str):
                try:
                    parsed.append(date.fromisoformat(value))
                except ValueError:
                    continue
        return sorted(parsed)

    def _fetch_chain(
        self, symbol: str, expiration: date, underlying_price: Decimal
    ) -> list[OptionContract]:
        payload = self._get(
            "/markets/options/chains",
            {"symbol": symbol, "expiration": expiration.isoformat(), "greeks": "true"},
        )
        options = payload.get("options")
        if not isinstance(options, Mapping):
            return []
        today = datetime.now(UTC).date()
        dte = max((expiration - today).days, 0)

        contracts: list[OptionContract] = []
        for row in _as_list(options.get("option")):
            if not isinstance(row, Mapping):
                continue
            contract = _parse_contract(row, expiration, dte, underlying_price)
            if contract is not None:
                contracts.append(contract)
        return contracts


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _parse_contract(
    row: Mapping[str, Any], expiration: date, dte: int, underlying_price: Decimal
) -> OptionContract | None:
    option_type_raw = row.get("option_type")
    if option_type_raw not in ("call", "put"):
        return None
    strike = _decimal(row.get("strike"))
    if strike is None or strike <= Decimal("0"):
        return None
    option_type = OptionType.CALL if option_type_raw == "call" else OptionType.PUT
    in_the_money = (
        strike < underlying_price if option_type is OptionType.CALL else strike > underlying_price
    )
    greeks = row.get("greeks")
    implied_volatility = _decimal(greeks.get("mid_iv")) if isinstance(greeks, Mapping) else None
    return OptionContract(
        contract_symbol=str(row.get("symbol", "")),
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        days_to_expiry=dte,
        last_price=_decimal(row.get("last")),
        bid=_decimal(row.get("bid")),
        ask=_decimal(row.get("ask")),
        volume=_int(row.get("volume")),
        open_interest=_int(row.get("open_interest")),
        implied_volatility=implied_volatility,
        in_the_money=in_the_money,
    )


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
