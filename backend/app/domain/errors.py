"""Domain exceptions raised before persistence or API boundaries are reached."""


class DomainValidationError(ValueError):
    """Raised when an entity would violate market, execution, or risk invariants."""
