"""Market data provider contracts and provider-level value objects."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from backend.app.domain.entities import Bar, CorporateAction
from backend.app.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class HistoricalMarketDataRequest:
    """Validated request for historical daily market data."""

    instrument_id: UUID
    symbol: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if not self.symbol.strip().isalnum():
            raise DomainValidationError("market data symbol must be alphanumeric")
        if self.end <= self.start:
            raise DomainValidationError("market data end date must be after start date")


@dataclass(frozen=True, slots=True)
class ProviderLineage:
    """Source metadata required for reproducible market-data ingestion."""

    provider: str
    dataset: str
    symbol: str
    adjustment_policy: str
    retrieved_at_utc_iso: str


@dataclass(frozen=True, slots=True)
class HistoricalMarketData:
    """Normalized provider response ready for quality checks and persistence."""

    request: HistoricalMarketDataRequest
    bars: Sequence[Bar]
    corporate_actions: Sequence[CorporateAction]
    lineage: ProviderLineage


class MarketDataProvider(Protocol):
    """Provider adapter contract implemented by Yahoo, Polygon, Tradier, IBKR, Alpaca, etc."""

    provider_name: str

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData: ...
