"""Independent deterministic research agents."""

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.agents.technical import (
    BreakoutAgent,
    MarketRegimeAgent,
    MeanReversionAgent,
    MomentumAgent,
    PortfolioAgent,
    RiskAgent,
    SupportResistanceAgent,
    TrendAgent,
    VolatilityAgent,
    VolumeAgent,
)

__all__ = [
    "BreakoutAgent",
    "MarketRegimeAgent",
    "MeanReversionAgent",
    "MomentumAgent",
    "PortfolioAgent",
    "RiskAgent",
    "SupportResistanceAgent",
    "TrendAgent",
    "VolatilityAgent",
    "VolumeAgent",
    "create_default_agents",
]
