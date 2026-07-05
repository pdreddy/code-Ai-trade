"""Strategy research lab endpoints."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from backend.app.application.strategy_lab import (
    DEFAULT_CAPITAL,
    DEFAULT_SYMBOLS,
    CorrelationCell,
    FeatureImportance,
    MonteCarloResult,
    PaperExportIntent,
    ParameterResult,
    RegimePerformance,
    StrategyLabReport,
    StrategyLabService,
    StrategyRun,
    StrategyTemplate,
    WalkForwardWindow,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])
CAPITAL_QUERY = Query(default=DEFAULT_CAPITAL, gt=0)


class StrategyTemplateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    short_window: int
    long_window: int
    description: str


class StrategyRunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: str
    symbol: str
    horizon_years: int
    total_return: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    trade_count: int
    exposure: Decimal
    score: Decimal


class WalkForwardResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: str
    symbol: str
    window: str
    start_date: date
    end_date: date
    return_pct: Decimal
    max_drawdown: Decimal


class MonteCarloResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: str
    symbol: str
    simulations: int
    median_return: Decimal
    fifth_percentile: Decimal
    ninety_fifth_percentile: Decimal
    probability_positive: Decimal


class ParameterResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str
    short_window: int
    long_window: int
    total_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    score: Decimal


class FeatureImportanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    feature: str
    importance: Decimal
    explanation: str


class CorrelationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    left: str
    right: str
    correlation: Decimal


class RegimePerformanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: str
    symbol: str
    regime: str
    observations: int
    average_return: Decimal
    hit_rate: Decimal


class PaperExportIntentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: str
    symbol: str
    action: str
    planned_execution: str
    capital: Decimal
    reason: str


class StrategyLabResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    generated_at: datetime
    horizon_years: int
    strategies: tuple[StrategyTemplateResponse, ...]
    leaderboard: tuple[StrategyRunResponse, ...]
    walk_forward: tuple[WalkForwardResponse, ...]
    monte_carlo: tuple[MonteCarloResponse, ...]
    parameter_optimizer: tuple[ParameterResponse, ...]
    feature_importance: tuple[FeatureImportanceResponse, ...]
    correlation_heatmap: tuple[CorrelationResponse, ...]
    regime_performance: tuple[RegimePerformanceResponse, ...]
    paper_export_intents: tuple[PaperExportIntentResponse, ...]


@router.get("/lab", response_model=StrategyLabResponse)
def strategy_lab(
    symbols: tuple[str, ...] = Query(default=DEFAULT_SYMBOLS, min_length=1, max_length=12),
    horizon_years: int = Query(default=5, ge=1, le=10),
    capital: Decimal = CAPITAL_QUERY,
) -> StrategyLabResponse:
    """Run multi-strategy comparison and optimization research."""

    try:
        report = StrategyLabService().build_report(
            symbols, horizon_years=horizon_years, capital=capital
        )
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Real strategy-lab provider access failed; no synthetic research was generated.",
        ) from exc
    return _report(report)


def _report(report: StrategyLabReport) -> StrategyLabResponse:
    return StrategyLabResponse(
        generated_at=report.generated_at,
        horizon_years=report.horizon_years,
        strategies=tuple(_strategy(item) for item in report.strategies),
        leaderboard=tuple(_run(item) for item in report.leaderboard),
        walk_forward=tuple(_walk(item) for item in report.walk_forward),
        monte_carlo=tuple(_monte(item) for item in report.monte_carlo),
        parameter_optimizer=tuple(_parameter(item) for item in report.parameter_optimizer),
        feature_importance=tuple(_feature(item) for item in report.feature_importance),
        correlation_heatmap=tuple(_correlation(item) for item in report.correlation_heatmap),
        regime_performance=tuple(_regime(item) for item in report.regime_performance),
        paper_export_intents=tuple(_paper_intent(item) for item in report.paper_export_intents),
    )


def _strategy(item: StrategyTemplate) -> StrategyTemplateResponse:
    return StrategyTemplateResponse(**item.__dict__)


def _run(item: StrategyRun) -> StrategyRunResponse:
    return StrategyRunResponse(**_rounded(item.__dict__))


def _walk(item: WalkForwardWindow) -> WalkForwardResponse:
    return WalkForwardResponse(**_rounded(item.__dict__))


def _monte(item: MonteCarloResult) -> MonteCarloResponse:
    return MonteCarloResponse(**_rounded(item.__dict__))


def _parameter(item: ParameterResult) -> ParameterResponse:
    return ParameterResponse(**_rounded(item.__dict__))


def _feature(item: FeatureImportance) -> FeatureImportanceResponse:
    return FeatureImportanceResponse(**_rounded(item.__dict__))


def _correlation(item: CorrelationCell) -> CorrelationResponse:
    return CorrelationResponse(**_rounded(item.__dict__))


def _regime(item: RegimePerformance) -> RegimePerformanceResponse:
    return RegimePerformanceResponse(**_rounded(item.__dict__))


def _paper_intent(item: PaperExportIntent) -> PaperExportIntentResponse:
    return PaperExportIntentResponse(**_rounded(item.__dict__))


def _rounded(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value.quantize(Decimal("0.0001")) if isinstance(value, Decimal) else value
        for key, value in payload.items()
    }
