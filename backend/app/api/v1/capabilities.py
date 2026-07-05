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
            area="Daily 0DTE options execution",
            status="blocked_by_provider",
            severity="critical",
            impact=(
                "CALL/PUT rows are research intents only; small/mid-cap daily expirations, "
                "premiums, Greeks, liquidity, and fills must be confirmed by provider."
            ),
            required_next_step=(
                "Add a real options-chain provider with bid/ask, IV, Greeks, volume, "
                "open interest, and expiration calendars before enabling daily 0DTE fills."
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
            area="News, unusual moves, fundamentals, and institutional flow",
            status="provider_missing",
            severity="high",
            impact=(
                "AI explanations are technical-first and cannot yet validate catalysts, "
                "earnings, unusual price/volume changes, options flow, or accumulation."
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


class ProviderCandidateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    category: str
    best_for: str
    capabilities: tuple[str, ...]
    integration_priority: str
    official_url: str


@router.get(
    "/platform/data-provider-candidates",
    response_model=tuple[ProviderCandidateResponse, ...],
)
def data_provider_candidates() -> tuple[ProviderCandidateResponse, ...]:
    """Return vetted alternative data feeds for Yahoo limitations."""

    return (
        ProviderCandidateResponse(
            provider="Databento",
            category="institutional_market_data",
            best_for="OPRA/equity options, equities, historical and real-time feeds",
            capabilities=("equities", "equity_options", "OPRA", "historical", "real_time"),
            integration_priority="primary_institutional_candidate",
            official_url="https://databento.com/options",
        ),
        ProviderCandidateResponse(
            provider="Tradier",
            category="brokerage_and_options_chain",
            best_for=(
                "option chains, strikes, expirations, IV/Greeks, "
                "and future paper/live routing"
            ),
            capabilities=("options_chains", "strikes", "expirations", "greeks", "brokerage"),
            integration_priority="fastest_options_brokerage_candidate",
            official_url="https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains",
        ),
        ProviderCandidateResponse(
            provider="Alpaca",
            category="market_data_and_brokerage",
            best_for="equities, options market data, and future paper brokerage integration",
            capabilities=("equities", "options", "historical", "real_time", "brokerage"),
            integration_priority="developer_friendly_candidate",
            official_url="https://docs.alpaca.markets/us/docs/historical-option-data",
        ),
        ProviderCandidateResponse(
            provider="Intrinio",
            category="options_analytics",
            best_for="realtime option chains, NBBO, trades, Greeks, IV, and unusual activity",
            capabilities=(
                "options_chains",
                "NBBO",
                "greeks",
                "implied_volatility",
                "unusual_activity",
            ),
            integration_priority="options_analytics_candidate",
            official_url="https://docs.intrinio.com/documentation/web_api/get_options_chain_realtime_v2",
        ),
        ProviderCandidateResponse(
            provider="Massive / Polygon",
            category="multi_asset_market_data",
            best_for="stocks, options trades/quotes/candles, Greeks/IV, news partner feeds",
            capabilities=("stocks", "options", "quotes", "candles", "greeks", "news"),
            integration_priority="broad_market_data_candidate",
            official_url="https://massive.com/options",
        ),
        ProviderCandidateResponse(
            provider="Benzinga",
            category="news_and_catalysts",
            best_for=(
                "market-moving news, real-time headlines, catalysts, "
                "and ticker-tagged stories"
            ),
            capabilities=("news", "headlines", "catalysts", "ticker_tags"),
            integration_priority="news_provider_candidate",
            official_url="https://docs.benzinga.com/introduction/welcome",
        ),
        ProviderCandidateResponse(
            provider="Finnhub",
            category="news_fundamentals_sentiment",
            best_for="company news, sentiment, fundamentals, and alternative data enrichment",
            capabilities=("company_news", "sentiment", "fundamentals", "alternative_data"),
            integration_priority="sentiment_and_fundamentals_candidate",
            official_url="https://finnhub.io/docs/api/company-news",
        ),
    )
