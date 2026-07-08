"""Massive.com options-chain snapshot adapter.

Massive's options snapshot endpoint returns a full chain with quotes, trades,
open interest, IV, and greeks in one paginated REST surface. This adapter keeps
that provider detail outside the application layer and converts the snapshot into
our provider-neutral ``OptionChain`` contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from backend.app.domain.options import OptionChain, OptionContract, OptionType

DEFAULT_TIMEOUT_SECONDS = 20
MASSIVE_BASE_URL = "https://api.massive.com"
MASSIVE_CHAIN_LIMIT = 250


class MassiveProviderError(RuntimeError):
    """Raised when Massive returns invalid, incomplete, or unavailable data."""


class MassiveOptionsProvider:
    """Massive.com implementation of the options-provider contract."""

    provider_name = "massive"

    def __init__(
        self,
        api_key: str,
        base_url: str = MASSIVE_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise MassiveProviderError("Massive API key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_option_chain(self, symbol: str, max_expiries: int = 3) -> OptionChain:
        upper = symbol.upper()
        payloads = self._fetch_pages(upper)
        today = datetime.now(UTC).date()
        rows = [row for payload in payloads for row in _results(payload)]
        expirations = sorted(
            {
                expiration
                for row in rows
                if (expiration := _expiration(row)) is not None and expiration >= today
            }
        )[: max(1, max_expiries)]
        allowed_expirations = set(expirations)

        contracts: list[OptionContract] = []
        underlying_price: Decimal | None = None
        for row in rows:
            if underlying_price is None:
                underlying_price = _underlying_price(row)
            contract = _parse_contract(row, today, allowed_expirations, underlying_price)
            if contract is not None:
                contracts.append(contract)

        if underlying_price is None or underlying_price <= Decimal("0"):
            raise MassiveProviderError(
                f"Massive option snapshot missing underlying price for {upper}"
            )

        return OptionChain(
            symbol=upper,
            underlying_price=underlying_price,
            retrieved_at_utc_iso=datetime.now(UTC).isoformat(),
            contracts=tuple(contracts),
        )

    def _fetch_pages(self, symbol: str) -> list[Mapping[str, Any]]:
        params = {
            "limit": str(MASSIVE_CHAIN_LIMIT),
            "sort": "expiration_date",
            "order": "asc",
        }
        url = self._url(f"/v3/snapshot/options/{symbol}", params)
        payloads: list[Mapping[str, Any]] = []
        for _ in range(20):
            payload = self._get_url(url, symbol)
            payloads.append(payload)
            next_url = payload.get("next_url")
            if not isinstance(next_url, str) or not next_url:
                break
            url = self._with_api_key(next_url)
        return payloads

    def _url(self, path: str, params: Mapping[str, str]) -> str:
        return self._with_api_key(f"{self._base_url}{path}?{urlencode(params)}")

    def _with_api_key(self, url: str) -> str:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["apiKey"] = self._api_key
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _get_url(self, url: str, symbol: str) -> Mapping[str, Any]:
        request = Request(url, headers={"Accept": "application/json"})  # noqa: S310
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                payload = cast(Mapping[str, Any], json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            raise MassiveProviderError(
                f"Massive rejected option snapshot for {symbol} with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise MassiveProviderError(
                f"Massive option snapshot request failed for {symbol}: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise MassiveProviderError(
                f"Massive returned invalid option snapshot JSON for {symbol}"
            ) from exc
        status = payload.get("status")
        if status not in (None, "OK"):
            raise MassiveProviderError(
                f"Massive option snapshot returned status {status} for {symbol}"
            )
        return payload


def _results(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return [row for row in results if isinstance(row, Mapping)]


def _expiration(row: Mapping[str, Any]) -> date | None:
    details = row.get("details")
    if not isinstance(details, Mapping):
        return None
    raw = details.get("expiration_date")
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _underlying_price(row: Mapping[str, Any]) -> Decimal | None:
    underlying = row.get("underlying_asset")
    if not isinstance(underlying, Mapping):
        return None
    return _decimal(underlying.get("price"))


def _parse_contract(
    row: Mapping[str, Any],
    today: date,
    allowed_expirations: set[date],
    underlying_price: Decimal | None,
) -> OptionContract | None:
    details = row.get("details")
    if not isinstance(details, Mapping):
        return None
    expiration = _expiration(row)
    if expiration is None or expiration not in allowed_expirations:
        return None
    option_type_raw = details.get("contract_type")
    if option_type_raw not in ("call", "put"):
        return None
    strike = _decimal(details.get("strike_price"))
    if strike is None or strike <= Decimal("0"):
        return None
    option_type = OptionType.CALL if option_type_raw == "call" else OptionType.PUT
    day = row.get("day")
    quote = row.get("last_quote")
    trade = row.get("last_trade")
    implied_volatility = _decimal(row.get("implied_volatility"))
    in_the_money = False
    if underlying_price is not None:
        in_the_money = (
            strike < underlying_price
            if option_type is OptionType.CALL
            else strike > underlying_price
        )
    return OptionContract(
        contract_symbol=str(details.get("ticker", "")),
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        days_to_expiry=max((expiration - today).days, 0),
        last_price=_decimal(trade.get("price")) if isinstance(trade, Mapping) else None,
        bid=_decimal(quote.get("bid")) if isinstance(quote, Mapping) else None,
        ask=_decimal(quote.get("ask")) if isinstance(quote, Mapping) else None,
        volume=_int(day.get("volume")) if isinstance(day, Mapping) else 0,
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
