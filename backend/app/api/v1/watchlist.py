"""Watchlist endpoint: real quotes and AI signals for many symbols at once.

Powers the Dashboard and Watchlists screens, which previously rendered bare
symbol links with no data. Each entry is a real provider quote plus the same
AI master decision the rest of the platform uses — no synthetic prices or
signals. A symbol whose data can't be fetched appears in `errors` rather than
being silently dropped.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import get_market_data_service
from backend.app.api.v1.portfolio import DEFAULT_UNIVERSE
from backend.app.application.market_data import MarketDataService
from backend.app.application.watchlist import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistQuoteResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    last_close: Decimal
    prior_close: Decimal | None
    change_pct: Decimal | None
    as_of: datetime
    action: str
    confidence: Decimal


class WatchlistErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    detail: str


class WatchlistResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str
    quotes: tuple[WatchlistQuoteResponse, ...]
    errors: tuple[WatchlistErrorResponse, ...]


@router.get("", response_model=WatchlistResponse)
def get_watchlist(
    service: Annotated[MarketDataService, Depends(get_market_data_service)],
    symbols: Annotated[list[str] | None, Query()] = None,
) -> WatchlistResponse:
    """Real last close, day-over-day change, and AI action for each symbol."""

    universe = symbols if symbols else list(DEFAULT_UNIVERSE)
    quotes, errors = WatchlistService(market_data=service).fetch(universe)
    return WatchlistResponse(
        generated_at=datetime.now().astimezone().isoformat(),
        quotes=tuple(
            WatchlistQuoteResponse(
                symbol=quote.symbol,
                last_close=quote.last_close,
                prior_close=quote.prior_close,
                change_pct=quote.change_pct,
                as_of=quote.as_of,
                action=quote.decision.action.value,
                confidence=quote.decision.confidence.value,
            )
            for quote in quotes
        ),
        errors=tuple(
            WatchlistErrorResponse(symbol=error.symbol, detail=error.detail) for error in errors
        ),
    )
