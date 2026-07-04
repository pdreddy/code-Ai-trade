"""Market-data API endpoints backed by real provider data."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.application.market_snapshot import (
    DEFAULT_SNAPSHOT_SYMBOLS,
    MarketSnapshot,
    MarketSnapshotService,
)

router = APIRouter(prefix="/market-data", tags=["market-data"])


class MarketSnapshotResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    start_date: date
    end_date: date
    bars: int
    last_close: Decimal
    total_return: Decimal
    cagr: Decimal
    max_drawdown: Decimal
    realized_volatility: Decimal


class MarketSnapshotsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: date
    snapshots: tuple[MarketSnapshotResponse, ...]


@router.get("/snapshots/five-year", response_model=MarketSnapshotsResponse)
def five_year_market_snapshots(
    symbols: tuple[str, ...] = Query(default=DEFAULT_SNAPSHOT_SYMBOLS, min_length=1, max_length=12),
) -> MarketSnapshotsResponse:
    """Return real five-year market snapshots from Yahoo chart data.

    The endpoint intentionally does not synthesize fallback prices. If provider access
    fails, callers receive a 503 and the UI keeps an honest unavailable state.
    """

    try:
        snapshots = MarketSnapshotService().five_year_snapshots(symbols)
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Real market-data provider access failed; no synthetic fallback was generated.",
        ) from exc
    return MarketSnapshotsResponse(
        generated_at=date.today(),
        snapshots=tuple(_response(snapshot) for snapshot in snapshots),
    )


def _response(snapshot: MarketSnapshot) -> MarketSnapshotResponse:
    return MarketSnapshotResponse(
        symbol=snapshot.symbol,
        start_date=snapshot.start_date,
        end_date=snapshot.end_date,
        bars=snapshot.bars,
        last_close=snapshot.last_close.quantize(Decimal("0.0001")),
        total_return=snapshot.total_return.quantize(Decimal("0.0001")),
        cagr=snapshot.cagr.quantize(Decimal("0.0001")),
        max_drawdown=snapshot.max_drawdown.quantize(Decimal("0.0001")),
        realized_volatility=snapshot.realized_volatility.quantize(Decimal("0.0001")),
    )
