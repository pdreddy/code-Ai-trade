"""Options research endpoint focused on 0DTE and weekly trading.

Returns near-term (0DTE / weekly) contracts, ranked unusual options activity, and
AI-aligned upcoming planned option trades for a symbol. The chain is real Yahoo
data; the direction of the planned trades comes from the same master decision that
drives the rest of the platform.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import (
    MasterDecisionResponse,
    _decision_response,
    get_market_data_service,
)
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_research import (
    DEFAULT_MAX_DTE,
    OptionsResearch,
    OptionsResearchService,
)
from backend.app.domain.options import OptionContract, OptionsProvider
from backend.app.infrastructure.providers.yahoo import YahooFinanceProviderError
from backend.app.infrastructure.providers.yahoo_options import YahooOptionsProvider

router = APIRouter(prefix="/options", tags=["options"])

SymbolPath = Annotated[str, Path(min_length=1, max_length=12)]
MaxDte = Annotated[int, Query(ge=0, le=45)]


def get_options_provider() -> OptionsProvider:
    """Provide the configured options provider (overridable in tests)."""

    return YahooOptionsProvider()


class OptionContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_symbol: str
    option_type: str
    strike: Decimal
    expiration: date
    days_to_expiry: int
    last_price: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    volume: int
    open_interest: int
    implied_volatility: Decimal | None
    in_the_money: bool
    volume_oi_ratio: Decimal


class UnusualContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract: OptionContractResponse
    volume_oi_ratio: Decimal


class PlannedOptionTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract: OptionContractResponse
    rationale: str


class OptionsResearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    underlying_price: Decimal
    as_of: str
    max_dte: int
    near_term_count: int
    zero_dte_count: int
    signal: MasterDecisionResponse
    unusual_activity: tuple[UnusualContractResponse, ...]
    planned_trades: tuple[PlannedOptionTradeResponse, ...]


@router.get("/{symbol}", response_model=OptionsResearchResponse)
def options_research(
    symbol: SymbolPath,
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    options: Annotated[OptionsProvider, Depends(get_options_provider)],
    max_dte: MaxDte = DEFAULT_MAX_DTE,
) -> OptionsResearchResponse:
    """Return near-term options, unusual activity, and AI-aligned planned trades."""

    service = OptionsResearchService(options=options, market_data=market_data)
    try:
        research = service.research(symbol, max_dte=max_dte)
    except YahooFinanceProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _research_response(research, max_dte)


def _contract_response(contract: OptionContract) -> OptionContractResponse:
    return OptionContractResponse(
        contract_symbol=contract.contract_symbol,
        option_type=contract.option_type.value,
        strike=contract.strike,
        expiration=contract.expiration,
        days_to_expiry=contract.days_to_expiry,
        last_price=contract.last_price,
        bid=contract.bid,
        ask=contract.ask,
        volume=contract.volume,
        open_interest=contract.open_interest,
        implied_volatility=contract.implied_volatility,
        in_the_money=contract.in_the_money,
        volume_oi_ratio=contract.volume_open_interest_ratio,
    )


def _research_response(research: OptionsResearch, max_dte: int) -> OptionsResearchResponse:
    return OptionsResearchResponse(
        symbol=research.symbol,
        underlying_price=research.underlying_price,
        as_of=research.as_of,
        max_dte=max_dte,
        near_term_count=research.near_term_count,
        zero_dte_count=research.zero_dte_count,
        signal=_decision_response(research.signal),
        unusual_activity=tuple(
            UnusualContractResponse(
                contract=_contract_response(item.contract),
                volume_oi_ratio=item.volume_oi_ratio,
            )
            for item in research.unusual_activity
        ),
        planned_trades=tuple(
            PlannedOptionTradeResponse(
                contract=_contract_response(item.contract),
                rationale=item.rationale,
            )
            for item in research.planned_trades
        ),
    )
