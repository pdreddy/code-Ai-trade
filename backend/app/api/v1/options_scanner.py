"""Cross-universe unusual options activity scanner endpoint.

Runs the same options research as the single-symbol Options tab concurrently
across a whole universe and merges the unusual-activity contracts into one
ranked list, so a user can see where the flow is right now without checking
each symbol individually. Real chain data only.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from backend.app.api.v1.market_data import get_market_data_service
from backend.app.api.v1.options import (
    OptionContractResponse,
    _contract_response,
    get_options_provider,
)
from backend.app.api.v1.options_portfolio import DEFAULT_UNIVERSE as SCANNER_UNIVERSE
from backend.app.application.market_data import MarketDataService
from backend.app.application.options_scanner import DEFAULT_TOP_N, OptionsScannerService
from backend.app.domain.options import OptionsProvider

router = APIRouter(prefix="/scanner", tags=["scanner"])

MaxDte = Annotated[int, Query(ge=0, le=45)]
TopN = Annotated[int, Query(ge=1, le=100)]


class ScannedUnusualContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    contract: OptionContractResponse
    volume_oi_ratio: Decimal


class ScannedPlannedTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    contract: OptionContractResponse
    rationale: str


class ScannerErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    detail: str


class OptionsScanResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str
    symbols_scanned: int
    unusual_activity: tuple[ScannedUnusualContractResponse, ...]
    planned_trades: tuple[ScannedPlannedTradeResponse, ...]
    errors: tuple[ScannerErrorResponse, ...]


@router.get("", response_model=OptionsScanResponse)
def scan_unusual_activity(
    market_data: Annotated[MarketDataService, Depends(get_market_data_service)],
    options: Annotated[OptionsProvider, Depends(get_options_provider)],
    symbols: Annotated[list[str] | None, Query()] = None,
    max_dte: MaxDte = 8,
    top_n: TopN = DEFAULT_TOP_N,
) -> OptionsScanResponse:
    """Scan the universe for unusual options activity and planned trades."""

    universe = symbols if symbols else list(SCANNER_UNIVERSE)
    result = OptionsScannerService(options=options, market_data=market_data).scan(
        universe, max_dte=max_dte, top_n=top_n
    )
    return OptionsScanResponse(
        generated_at=datetime.now().astimezone().isoformat(),
        symbols_scanned=result.symbols_scanned,
        unusual_activity=tuple(
            ScannedUnusualContractResponse(
                symbol=item.symbol,
                contract=_contract_response(item.contract),
                volume_oi_ratio=item.volume_oi_ratio,
            )
            for item in result.unusual_activity
        ),
        planned_trades=tuple(
            ScannedPlannedTradeResponse(
                symbol=item.symbol,
                contract=_contract_response(item.contract),
                rationale=item.rationale,
            )
            for item in result.planned_trades
        ),
        errors=tuple(
            ScannerErrorResponse(symbol=error.symbol, detail=error.detail)
            for error in result.errors
        ),
    )
