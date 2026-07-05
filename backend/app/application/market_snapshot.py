"""Five-year market snapshot service backed by real provider chart data."""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from statistics import pstdev

TRADING_DAYS = Decimal("252")
MIN_BARS = 2
DEFAULT_SNAPSHOT_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")


@dataclass(frozen=True, slots=True)
class SnapshotBar:
    timestamp: datetime
    close: Decimal


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    start_date: date
    end_date: date
    bars: int
    last_close: Decimal
    total_return: Decimal
    cagr: Decimal
    max_drawdown: Decimal
    realized_volatility: Decimal


class MarketSnapshotService:
    """Build real historical ETF snapshots without storing or fabricating prices."""

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        self._timeout_seconds = timeout_seconds

    def five_year_snapshots(
        self,
        symbols: tuple[str, ...] = DEFAULT_SNAPSHOT_SYMBOLS,
        *,
        end: date | None = None,
    ) -> tuple[MarketSnapshot, ...]:
        resolved_end = end or datetime.now(UTC).date()
        start = resolved_end - timedelta(days=365 * 5 + 2)
        return tuple(self._snapshot(symbol.upper(), start, resolved_end) for symbol in symbols)

    def _snapshot(self, symbol: str, start: date, end: date) -> MarketSnapshot:
        bars = self._fetch_bars(symbol, start, end)
        if len(bars) < MIN_BARS:
            msg = f"not enough bars returned for {symbol}"
            raise RuntimeError(msg)
        closes = [bar.close for bar in bars]
        daily_returns = [
            float(closes[index] / closes[index - 1] - 1) for index in range(1, len(closes))
        ]
        total_return = closes[-1] / closes[0] - 1
        years = Decimal(len(closes)) / TRADING_DAYS
        cagr = Decimal(str((float(closes[-1] / closes[0]) ** (1 / float(years))) - 1))
        volatility = Decimal(str(pstdev(daily_returns) * math.sqrt(float(TRADING_DAYS))))
        return MarketSnapshot(
            symbol=symbol,
            start_date=bars[0].timestamp.date(),
            end_date=bars[-1].timestamp.date(),
            bars=len(bars),
            last_close=closes[-1],
            total_return=total_return,
            cagr=cagr,
            max_drawdown=self._max_drawdown(closes),
            realized_volatility=volatility,
        )

    def _fetch_bars(self, symbol: str, start: date, end: date) -> list[SnapshotBar]:
        period1 = int(datetime.combine(start, time.min, tzinfo=UTC).timestamp())
        period2 = int(datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC).timestamp())
        query = urllib.parse.urlencode(
            {
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "history",
                "includeAdjustedClose": "true",
            }
        )
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "ai-quant-platform/0.1"})
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read())
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        bars: list[SnapshotBar] = []
        for raw_timestamp, close in zip(timestamps, closes, strict=True):
            if close is None:
                continue
            bars.append(
                SnapshotBar(
                    timestamp=datetime.fromtimestamp(raw_timestamp, tz=UTC),
                    close=Decimal(str(close)),
                )
            )
        return bars

    @staticmethod
    def _max_drawdown(closes: list[Decimal]) -> Decimal:
        peak = closes[0]
        max_drawdown = Decimal("0")
        for close in closes:
            peak = max(peak, close)
            drawdown = close / peak - 1
            max_drawdown = min(max_drawdown, drawdown)
        return max_drawdown
