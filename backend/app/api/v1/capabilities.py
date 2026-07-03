"""Capability endpoints for production-readiness discovery."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["capabilities"])


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str
    status: str
    details: tuple[str, ...]


@router.get("/backtests/capabilities", response_model=CapabilityResponse)
def backtest_capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        capability="event_driven_backtesting",
        status="application_service_ready",
        details=(
            "signal_on_close_fill_next_open",
            "equity_drawdown_monthly_returns",
            "trade_list_and_performance_metrics",
        ),
    )


@router.get("/paper-trading/capabilities", response_model=CapabilityResponse)
def paper_trading_capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        capability="paper_trading",
        status="application_service_ready",
        details=("pending_filled_cancelled_rejected_orders", "cash_positions_trades"),
    )


@router.get("/risk/capabilities", response_model=CapabilityResponse)
def risk_capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        capability="risk_engine",
        status="application_service_ready",
        details=("kill_switch", "exposure", "drawdown", "liquidity", "correlation"),
    )
