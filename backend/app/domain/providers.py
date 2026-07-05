"""Market, options, and news provider contracts and provider-level value objects."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from backend.app.domain.entities import Bar, CorporateAction
from backend.app.domain.errors import DomainValidationError

OptionRight = Literal["CALL", "PUT"]


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


@dataclass(frozen=True, slots=True)
class OptionChainRequest:
    """Validated request for option contracts on one underlying and expiration."""

    symbol: str
    expiration: date
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.symbol.strip().isalnum():
            raise DomainValidationError("option chain symbol must be alphanumeric")
        if self.expiration < self.as_of.date():
            raise DomainValidationError("option expiration cannot be before as_of date")


@dataclass(frozen=True, slots=True)
class OptionContract:
    """Normalized listed option contract metadata."""

    symbol: str
    underlying_symbol: str
    expiration: date
    strike: Decimal
    right: OptionRight

    def __post_init__(self) -> None:
        if self.strike <= 0:
            raise DomainValidationError("option strike must be positive")


@dataclass(frozen=True, slots=True)
class OptionQuote:
    """Normalized option market quote required before paper option fills."""

    contract: OptionContract
    bid: Decimal
    ask: Decimal
    last: Decimal | None
    volume: int
    open_interest: int
    implied_volatility: Decimal | None
    delta: Decimal | None
    gamma: Decimal | None
    theta: Decimal | None
    vega: Decimal | None
    quoted_at: datetime

    def __post_init__(self) -> None:
        if self.bid < 0 or self.ask < 0:
            raise DomainValidationError("option bid/ask cannot be negative")
        if self.ask and self.bid > self.ask:
            raise DomainValidationError("option bid cannot exceed ask")
        if self.volume < 0 or self.open_interest < 0:
            raise DomainValidationError("option liquidity fields cannot be negative")


@dataclass(frozen=True, slots=True)
class OptionChain:
    """Provider-normalized option chain with lineage for auditability."""

    request: OptionChainRequest
    quotes: Sequence[OptionQuote]
    lineage: ProviderLineage


@dataclass(frozen=True, slots=True)
class NewsCatalystRequest:
    """Validated request for ticker-tagged news and catalyst events."""

    symbols: tuple[str, ...]
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not self.symbols:
            raise DomainValidationError("news catalyst symbols cannot be empty")
        if any(not symbol.strip().isalnum() for symbol in self.symbols):
            raise DomainValidationError("news catalyst symbols must be alphanumeric")
        if self.end <= self.start:
            raise DomainValidationError("news catalyst end must be after start")


@dataclass(frozen=True, slots=True)
class NewsCatalyst:
    """Ticker-tagged external event usable by research without future leakage."""

    symbol: str
    headline: str
    source: str
    published_at: datetime
    url: str | None
    sentiment_score: Decimal | None
    relevance_score: Decimal | None

    def __post_init__(self) -> None:
        if not self.symbol.strip().isalnum():
            raise DomainValidationError("news catalyst symbol must be alphanumeric")
        if not self.headline.strip():
            raise DomainValidationError("news catalyst headline cannot be empty")


@dataclass(frozen=True, slots=True)
class NewsCatalystBatch:
    """Provider-normalized news/catalyst response with source lineage."""

    request: NewsCatalystRequest
    catalysts: Sequence[NewsCatalyst]
    lineage: ProviderLineage


class MarketDataProvider(Protocol):
    """Provider adapter contract implemented by Yahoo, Polygon, Tradier, IBKR, Alpaca, etc."""

    provider_name: str

    def fetch_daily_history(self, request: HistoricalMarketDataRequest) -> HistoricalMarketData: ...


class OptionsDataProvider(Protocol):
    """Provider contract required before 0DTE option intents can become paper fills."""

    provider_name: str

    def fetch_option_chain(self, request: OptionChainRequest) -> OptionChain: ...


class NewsCatalystProvider(Protocol):
    """Provider contract for news, unusual moves, sentiment, and catalyst validation."""

    provider_name: str

    def fetch_catalysts(self, request: NewsCatalystRequest) -> NewsCatalystBatch: ...
