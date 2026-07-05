"""Agent registry construction."""

from backend.app.application.agents.technical import (
    BreakoutAgent,
    MarketRegimeAgent,
    MeanReversionAgent,
    MomentumAgent,
    PortfolioAgent,
    RallyBasePatternAgent,
    RiskAgent,
    SupplyDemandAgent,
    SupportResistanceAgent,
    TrendAgent,
    VolatilityAgent,
    VolumeAgent,
)
from backend.app.domain.agents import TradingAgent


def create_default_agents() -> tuple[TradingAgent, ...]:
    """Return the complete V1 independent agent set in deterministic order."""

    return (
        TrendAgent(),
        MomentumAgent(),
        VolatilityAgent(),
        RiskAgent(),
        PortfolioAgent(),
        MeanReversionAgent(),
        BreakoutAgent(),
        RallyBasePatternAgent(),
        SupplyDemandAgent(),
        SupportResistanceAgent(),
        VolumeAgent(),
        MarketRegimeAgent(),
    )
