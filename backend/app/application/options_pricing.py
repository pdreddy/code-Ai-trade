"""Black-Scholes option pricing and a realized-volatility estimator.

There is no free historical options-quote data source wired into this platform
(Yahoo's chain endpoint only serves the *current* live chain — see
``yahoo_options.py``). To backtest a 0DTE/weekly options strategy over real
multi-year history, contract premiums are therefore priced theoretically with
Black-Scholes off real historical underlying closes, using a realized-volatility
proxy for implied vol. This is standard quant-research practice when historical
options tick data is unavailable, but it must never be confused with real quoted
option prices: every response that uses this module labels itself as a *modeled*
backtest, and the live Options tab (real Yahoo chain quotes) is kept completely
separate from it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.app.domain.errors import DomainValidationError

TRADING_DAYS_PER_YEAR = 252

# Floors avoid degenerate Black-Scholes inputs (division by zero / log of zero)
# without materially distorting the price: a fully flat realized-vol window still
# implies *some* residual uncertainty, and a 0DTE contract still has a few hours
# of intraday time value left when it is opened at the day's open.
MIN_SIGMA = Decimal("0.05")
MIN_YEARS_TO_EXPIRY = Decimal("1") / Decimal("365") / Decimal("4")  # ~6 intraday hours


class OptionSide(StrEnum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True, slots=True)
class BlackScholesInputs:
    spot: Decimal
    strike: Decimal
    years_to_expiry: Decimal
    risk_free_rate: Decimal
    volatility: Decimal
    side: OptionSide

    def __post_init__(self) -> None:
        if self.spot <= Decimal("0") or self.strike <= Decimal("0"):
            raise DomainValidationError("spot and strike must be positive")
        if self.years_to_expiry < Decimal("0"):
            raise DomainValidationError("years to expiry cannot be negative")
        if self.volatility < Decimal("0"):
            raise DomainValidationError("volatility cannot be negative")


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def intrinsic_value(spot: Decimal, strike: Decimal, side: OptionSide) -> Decimal:
    """Payoff if the contract is held to expiry with the given spot at settlement."""

    if side is OptionSide.CALL:
        return max(spot - strike, Decimal("0"))
    return max(strike - spot, Decimal("0"))


def black_scholes_price(inputs: BlackScholesInputs) -> Decimal:
    """Theoretical European option premium; collapses to intrinsic value at T=0."""

    if inputs.years_to_expiry <= Decimal("0"):
        return intrinsic_value(inputs.spot, inputs.strike, inputs.side)

    spot = float(inputs.spot)
    strike = float(inputs.strike)
    years = float(max(inputs.years_to_expiry, MIN_YEARS_TO_EXPIRY))
    rate = float(inputs.risk_free_rate)
    sigma = float(max(inputs.volatility, MIN_SIGMA))

    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma**2) * years) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    discount = math.exp(-rate * years)

    if inputs.side is OptionSide.CALL:
        price = spot * _normal_cdf(d1) - strike * discount * _normal_cdf(d2)
    else:
        price = strike * discount * _normal_cdf(-d2) - spot * _normal_cdf(-d1)

    # Numerical noise can push a deep-OTM price fractionally negative; floor at 0.
    return max(Decimal(str(round(price, 4))), Decimal("0"))


MIN_WINDOW_SIZE = 3
MIN_RETURN_SAMPLE = 2


def realized_volatility(
    closes: Sequence[Decimal], lookback: int = 20
) -> Decimal:
    """Annualized stdev of daily log returns over the trailing window.

    Used as the implied-volatility proxy for the Black-Scholes pricer since no
    historical implied-vol series exists for these underlyings.
    """

    window = closes[-(lookback + 1) :]
    if len(window) < MIN_WINDOW_SIZE:
        return MIN_SIGMA
    log_returns = [
        math.log(float(window[i]) / float(window[i - 1]))
        for i in range(1, len(window))
        if window[i - 1] > Decimal("0") and window[i] > Decimal("0")
    ]
    if len(log_returns) < MIN_RETURN_SAMPLE:
        return MIN_SIGMA
    mean = sum(log_returns) / len(log_returns)
    variance = sum((value - mean) ** 2 for value in log_returns) / (len(log_returns) - 1)
    annualized = math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)
    return max(Decimal(str(round(annualized, 4))), MIN_SIGMA)


def round_to_strike_increment(spot: Decimal) -> Decimal:
    """Snap a spot price to a realistic at-the-money strike increment.

    Real listed strikes step by $0.50-$1 under $25, $1 up to ~$200, and $5 above
    that. This keeps modeled strikes plausible rather than using the raw spot.
    """

    if spot < Decimal("25"):
        increment = Decimal("0.5")
    elif spot < Decimal("200"):
        increment = Decimal("1")
    else:
        increment = Decimal("5")
    return (spot / increment).to_integral_value(rounding="ROUND_HALF_EVEN") * increment
