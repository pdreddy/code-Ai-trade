"""Analytics API endpoints that compute summaries from caller-supplied real results."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from backend.app.application.analytics import AnalyticsService
from backend.app.domain.entities import Trade
from backend.app.domain.value_objects import Price, Quantity

router = APIRouter(prefix="/analytics", tags=["analytics"])


class TradeInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    instrument_id: UUID
    entry_order_id: UUID
    exit_order_id: UUID | None
    entry_at: datetime
    entry_price: Decimal
    quantity: Decimal
    exit_at: datetime | None = None
    exit_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    reason: str | None = None


class TradeAnalyticsRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    trades: tuple[TradeInput, ...]


class TradeAnalyticsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    trade_count: int
    closed_trade_count: int
    win_count: int
    loss_count: int
    success_rate: Decimal
    average_realized_pnl: Decimal
    total_realized_pnl: Decimal


@router.post("/trades/summary", response_model=TradeAnalyticsResponse)
def summarize_trades(request: TradeAnalyticsRequest) -> TradeAnalyticsResponse:
    """Summarize real trade records supplied by a caller; no synthetic data is generated."""

    trades = tuple(
        Trade(
            id=trade.id,
            instrument_id=trade.instrument_id,
            entry_order_id=trade.entry_order_id,
            exit_order_id=trade.exit_order_id,
            entry_at=trade.entry_at,
            entry_price=Price(trade.entry_price),
            quantity=Quantity(trade.quantity),
            exit_at=trade.exit_at,
            exit_price=Price(trade.exit_price) if trade.exit_price is not None else None,
            realized_pnl=trade.realized_pnl,
            reason=trade.reason,
        )
        for trade in request.trades
    )
    analytics = AnalyticsService().trade_analytics(trades)
    return TradeAnalyticsResponse(
        trade_count=analytics.trade_count,
        closed_trade_count=analytics.closed_trade_count,
        win_count=analytics.win_count,
        loss_count=analytics.loss_count,
        success_rate=analytics.success_rate,
        average_realized_pnl=analytics.average_realized_pnl,
        total_realized_pnl=analytics.total_realized_pnl,
    )
