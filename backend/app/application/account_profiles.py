"""Named account-size profiles for position sizing.

These change nothing about the AI strategy, signals, or risk rules — only how
much capital is deployed. Both the stock and options portfolio executions
already size positions (share/contract counts) off whatever capital they're
given, so a profile is just a named, friendlier preset over that existing
`capital` parameter — the same way a real trader with $500 sizes differently
than one with $100,000, without trading a different system.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AccountProfile:
    key: str
    label: str
    capital: Decimal
    description: str


ACCOUNT_PROFILES: tuple[AccountProfile, ...] = (
    AccountProfile(
        key="small",
        label="Small ($500)",
        capital=Decimal("500"),
        description=(
            "A small, real-money-sized account. Position sizing is tight — some "
            "symbols may sit in cash all window when a share or contract doesn't "
            "fit the budget, and a losing options trade can leave too little cash "
            "to open the next one. That is a realistic outcome, not a bug."
        ),
    ),
    AccountProfile(
        key="medium",
        label="Medium ($10,000)",
        capital=Decimal("10000"),
        description="The platform's default account size, used throughout the rest of the app.",
    ),
    AccountProfile(
        key="large",
        label="Large ($100,000)",
        capital=Decimal("100000"),
        description=(
            "A larger account with room to size positions across the full "
            "universe without cash constraints limiting which signals are acted on."
        ),
    ),
)

ACCOUNT_PROFILES_BY_KEY: dict[str, AccountProfile] = {
    profile.key: profile for profile in ACCOUNT_PROFILES
}


def get_account_profile(key: str) -> AccountProfile:
    try:
        return ACCOUNT_PROFILES_BY_KEY[key]
    except KeyError as exc:
        valid = ", ".join(ACCOUNT_PROFILES_BY_KEY)
        raise ValueError(f"Unknown account profile '{key}'. Valid profiles: {valid}") from exc
