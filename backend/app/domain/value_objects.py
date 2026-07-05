"""Immutable value objects used by the quantitative domain model."""

from dataclasses import dataclass
from decimal import Decimal

from backend.app.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Price:
    """Positive monetary price with Decimal precision."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value <= Decimal("0"):
            raise DomainValidationError("price must be positive")


@dataclass(frozen=True, slots=True)
class Quantity:
    """Positive share quantity represented with Decimal for fractional support."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value <= Decimal("0"):
            raise DomainValidationError("quantity must be positive")


@dataclass(frozen=True, slots=True)
class Confidence:
    """Normalized confidence in the closed interval [0, 1]."""

    value: Decimal

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.value <= Decimal("1"):
            raise DomainValidationError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RiskFraction:
    """Normalized risk fraction in the closed interval [0, 1]."""

    value: Decimal

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.value <= Decimal("1"):
            raise DomainValidationError("risk fraction must be between 0 and 1")
