"""Yahoo Finance market-data provider adapter.

The adapter uses Yahoo's chart endpoint and converts the response into domain bars,
corporate actions, and provider lineage. It performs no persistence and contains no
trading logic.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from backend.app.domain.entities import Bar, CorporateAction
from backend.app.domain.enums import CorporateActionType
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import (
    HistoricalMarketData,
    HistoricalMarketDataRequest,
    ProviderLineage,
)
from backend.app.domain.value_objects import Price

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
DEFAULT_TIMEOUT_SECONDS = 20
ADJUSTMENT_POLICY = "raw_ohlcv_with_adjusted_close"
YAHOO_SOURCE = "yahoo.chart.v8"


class YahooFinanceProviderError(RuntimeError):
    """Raised when Yahoo Finance returns invalid, incomplete, or unavailable data."""


class YahooFinanceProvider:
    """Yahoo Finance implementation of the market-data provider contract."""

    provider_name = "yahoo"

    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0:
            raise DomainValidationError("Yahoo provider timeout must be positive")
        self._timeout_seconds = timeout_seconds

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData:
        payload = self._get_chart_payload(request)
        result = _extract_result(payload, request.symbol)
        bars = _parse_bars(result, request)
        corporate_actions = _parse_corporate_actions(result, request)
        retrieved_at = datetime.now(UTC).isoformat()
        lineage = ProviderLineage(
            provider=self.provider_name,
            dataset="chart/v8",
            symbol=request.symbol.upper(),
            adjustment_policy=ADJUSTMENT_POLICY,
            retrieved_at_utc_iso=retrieved_at,
        )
        return HistoricalMarketData(
            request=request,
            bars=bars,
            corporate_actions=corporate_actions,
            lineage=lineage,
        )

    def _get_chart_payload(self, request: HistoricalMarketDataRequest) -> Mapping[str, Any]:
        period1 = _date_to_epoch_seconds(request.start)
        period2 = _date_to_epoch_seconds(request.end)
        query = urlencode(
            {
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            }
        )
        url = f"{YAHOO_CHART_URL.format(symbol=request.symbol.upper())}?{query}"
        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
                return cast(Mapping[str, Any], payload)
        except HTTPError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance rejected {request.symbol.upper()} with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance request failed for {request.symbol.upper()}: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise YahooFinanceProviderError(
                f"Yahoo Finance returned invalid JSON for {request.symbol.upper()}"
            ) from exc


def _date_to_epoch_seconds(value: date) -> int:
    return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp())


def _extract_result(payload: Mapping[str, Any], symbol: str) -> Mapping[str, Any]:
    chart = payload.get("chart")
    if not isinstance(chart, Mapping):
        raise YahooFinanceProviderError(
            f"Yahoo Finance response missing chart for {symbol.upper()}"
        )
    error = chart.get("error")
    if error is not None:
        raise YahooFinanceProviderError(
            f"Yahoo Finance returned an error for {symbol.upper()}: {error}"
        )
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        raise YahooFinanceProviderError(f"Yahoo Finance returned no result for {symbol.upper()}")
    result = results[0]
    if not isinstance(result, Mapping):
        raise YahooFinanceProviderError(f"Yahoo Finance result was malformed for {symbol.upper()}")
    return result


def _parse_bars(result: Mapping[str, Any], request: HistoricalMarketDataRequest) -> tuple[Bar, ...]:
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, Mapping):
        raise YahooFinanceProviderError(
            f"Yahoo Finance bars missing timestamps for {request.symbol.upper()}"
        )
    quote_series = indicators.get("quote")
    adjusted_series = indicators.get("adjclose")
    if not isinstance(quote_series, list) or not quote_series:
        raise YahooFinanceProviderError(
            f"Yahoo Finance bars missing quote data for {request.symbol.upper()}"
        )
    quote = quote_series[0]
    adjusted = adjusted_series[0] if isinstance(adjusted_series, list) and adjusted_series else {}
    if not isinstance(quote, Mapping):
        raise YahooFinanceProviderError(
            f"Yahoo Finance quote data malformed for {request.symbol.upper()}"
        )
    adjusted_close_values = adjusted.get("adjclose") if isinstance(adjusted, Mapping) else None

    bars: list[Bar] = []
    for index, epoch_value in enumerate(timestamps):
        values = _quote_values_at(quote, adjusted_close_values, index, request.symbol)
        if values is None:
            continue
        timestamp = datetime.fromtimestamp(int(epoch_value), tz=UTC)
        bars.append(
            Bar(
                instrument_id=request.instrument_id,
                timestamp=timestamp,
                open=Price(values.open),
                high=Price(values.high),
                low=Price(values.low),
                close=Price(values.close),
                volume=values.volume,
                adjusted_close=(
                    Price(values.adjusted_close)
                    if values.adjusted_close is not None
                    else None
                ),
            )
        )
    if not bars:
        raise YahooFinanceProviderError(
            f"Yahoo Finance returned no complete bars for {request.symbol.upper()}"
        )
    return tuple(bars)


@dataclass(frozen=True, slots=True)
class _QuoteValues:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted_close: Decimal | None


def _quote_values_at(
    quote: Mapping[str, Any], adjusted_close_values: Any, index: int, symbol: str
) -> _QuoteValues | None:
    open_value = _decimal_at(quote, "open", index)
    high = _decimal_at(quote, "high", index)
    low = _decimal_at(quote, "low", index)
    close = _decimal_at(quote, "close", index)
    volume = _int_at(quote, "volume", index)
    adjusted_close = _decimal_from_sequence(adjusted_close_values, index)
    if (
        open_value is None
        or high is None
        or low is None
        or close is None
        or volume is None
    ):
        return None
    return _QuoteValues(
        open=open_value,
        high=high,
        low=low,
        close=close,
        volume=volume,
        adjusted_close=adjusted_close,
    )


def _decimal_at(quote: Mapping[str, Any], key: str, index: int) -> Decimal | None:
    values = quote.get(key)
    return _decimal_from_sequence(values, index)


def _decimal_from_sequence(values: Any, index: int) -> Decimal | None:
    if not isinstance(values, list) or index >= len(values) or values[index] is None:
        return None
    return Decimal(str(values[index]))


def _int_at(quote: Mapping[str, Any], key: str, index: int) -> int | None:
    values = quote.get(key)
    if not isinstance(values, list) or index >= len(values) or values[index] is None:
        return None
    return int(values[index])


def _parse_corporate_actions(
    result: Mapping[str, Any], request: HistoricalMarketDataRequest
) -> tuple[CorporateAction, ...]:
    events = result.get("events")
    if not isinstance(events, Mapping):
        return ()
    actions: list[CorporateAction] = []
    dividends = events.get("dividends")
    if isinstance(dividends, Mapping):
        for event in dividends.values():
            if isinstance(event, Mapping):
                amount = event.get("amount")
                epoch_date = event.get("date")
                if amount is not None and epoch_date is not None:
                    actions.append(
                        CorporateAction(
                            instrument_id=request.instrument_id,
                            ex_date=datetime.fromtimestamp(int(epoch_date), tz=UTC).date(),
                            action_type=CorporateActionType.DIVIDEND,
                            value=Decimal(str(amount)),
                            source=YAHOO_SOURCE,
                        )
                    )
    splits = events.get("splits")
    if isinstance(splits, Mapping):
        for event in splits.values():
            if isinstance(event, Mapping):
                numerator = event.get("numerator")
                denominator = event.get("denominator")
                epoch_date = event.get("date")
                if numerator is not None and denominator is not None and epoch_date is not None:
                    actions.append(
                        CorporateAction(
                            instrument_id=request.instrument_id,
                            ex_date=datetime.fromtimestamp(int(epoch_date), tz=UTC).date(),
                            action_type=CorporateActionType.SPLIT,
                            value=Decimal(str(numerator)) / Decimal(str(denominator)),
                            source=YAHOO_SOURCE,
                        )
                    )
    return tuple(sorted(actions, key=lambda action: (action.ex_date, action.action_type.value)))

