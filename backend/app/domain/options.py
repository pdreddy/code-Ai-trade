"""Domain types for option-chain research (0DTE and weekly focus).

These are provider-neutral value objects. An options provider adapter converts an
upstream chain into an ``OptionChain``; the application layer combines it with the
AI signal to surface unusual activity and forward-looking planned option trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from backend.app.domain.errors import DomainValidationError


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True, slots=True)
class OptionContract:
    contract_symbol: str
    option_type: OptionType
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

    def __post_init__(self) -> None:
        if self.strike <= Decimal("0"):
            raise DomainValidationError("option strike must be positive")
        if self.volume < 0 or self.open_interest < 0:
            raise DomainValidationError("option volume and open interest cannot be negative")
        if self.days_to_expiry < 0:
            raise DomainValidationError("option days-to-expiry cannot be negative")

    @property
    def volume_open_interest_ratio(self) -> Decimal:
        """Volume relative to standing open interest.

        A ratio above 1 means more contracts traded today than were previously
        open — the classic footprint of unusual options activity.
        """

        if self.open_interest <= 0:
            return Decimal(self.volume)
        return (Decimal(self.volume) / Decimal(self.open_interest)).quantize(Decimal("0.01"))


@dataclass(frozen=True, slots=True)
class OptionChain:
    symbol: str
    underlying_price: Decimal
    retrieved_at_utc_iso: str
    contracts: tuple[OptionContract, ...]


class OptionsProvider(Protocol):
    """Contract for adapters that return an option chain for a symbol."""

    def fetch_option_chain(self, symbol: str, max_expiries: int) -> OptionChain: ...
