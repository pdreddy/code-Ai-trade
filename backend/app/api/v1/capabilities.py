"""Capability endpoints for production-readiness discovery."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["capabilities"])


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability: str
    status: str
    details: tuple[str, ...]


class ReadinessGapResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    area: str
    status: str
    severity: str
    impact: str
    required_next_step: str


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


@router.get("/platform/readiness-gaps", response_model=tuple[ReadinessGapResponse, ...])
def platform_readiness_gaps() -> tuple[ReadinessGapResponse, ...]:
    """Return the honest production-readiness gaps the UI should surface to users."""

    return (
        ReadinessGapResponse(
            area="0DTE options execution",
            status="blocked_by_provider",
            severity="critical",
            impact=(
                "CALL/PUT rows are research intents only; premiums, Greeks, liquidity, "
                "and fills are not available."
            ),
            required_next_step=(
                "Add a real options-chain provider with bid/ask, IV, Greeks, volume, "
                "open interest, and expiration calendars before enabling paper options fills."
            ),
        ),
        ReadinessGapResponse(
            area="Persistent paper-trading ledger",
            status="adapter_ready_not_wired_to_runtime",
            severity="high",
            impact=(
                "Daily report paper trades are reproducible simulations, not a "
                "continuously persisted account ledger."
            ),
            required_next_step=(
                "Wire the paper broker to execution/risk repositories and expose "
                "account-scoped order, fill, position, and trade endpoints."
            ),
        ),
        ReadinessGapResponse(
            area="News, fundamentals, and institutional flow",
            status="provider_missing",
            severity="high",
            impact=(
                "AI explanations are technical-first and cannot yet validate catalysts, "
                "earnings, options flow, or institutional accumulation."
            ),
            required_next_step=(
                "Add configured providers for news, fundamentals, filings, options flow, "
                "and sentiment with source lineage."
            ),
        ),
        ReadinessGapResponse(
            area="Interactive charts and terminal tables",
            status="ui_foundation_ready",
            severity="medium",
            impact=(
                "Current charts are lightweight summaries rather than full "
                "TradingView-style interactive research workspaces."
            ),
            required_next_step=(
                "Integrate chart/table libraries against existing equity, drawdown, "
                "holdings, trade, and benchmark DTOs."
            ),
        ),
        ReadinessGapResponse(
            area="Live brokerage execution",
            status="intentionally_disabled",
            severity="critical",
            impact=(
                "The platform cannot send live orders, which prevents accidental "
                "real-money trading during research hardening."
            ),
            required_next_step=(
                "After paper ledger, risk approvals, audit logging, and broker adapters "
                "are complete, gate live trading behind explicit configuration and "
                "kill-switch controls."
            ),
        ),
    )
