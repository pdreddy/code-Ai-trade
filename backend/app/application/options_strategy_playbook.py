"""Deterministic options strategy playbook used before any AI overlay.

These are named strategy building blocks with explicit market setup, required data,
and risk rules. They are intentionally deterministic: the platform can expose and
scan these first, then layer AI ranking on top later.
"""

from dataclasses import dataclass
from enum import StrEnum


class OptionsStrategyKey(StrEnum):
    UNUSUAL_OPTIONS_FLOW = "unusual_options_flow"
    OPENING_RANGE_BREAKOUT = "opening_range_breakout"
    GAMMA_SQUEEZE = "gamma_squeeze"
    IV_CRUSH = "iv_crush"
    EARNINGS_MOMENTUM = "earnings_momentum"
    WHEEL = "wheel"
    CREDIT_SPREAD_SCANNER = "credit_spread_scanner"
    DEBIT_SPREAD_SCANNER = "debit_spread_scanner"
    ZERO_DTE_SPX = "zero_dte_spx"
    SPY_MOMENTUM = "spy_momentum"


@dataclass(frozen=True, slots=True)
class OptionsStrategyPlaybookItem:
    key: OptionsStrategyKey
    label: str
    objective: str
    setup: tuple[str, ...]
    required_data: tuple[str, ...]
    risk_rules: tuple[str, ...]
    preferred_symbols: tuple[str, ...]
    scanner_ready: bool


OPTIONS_STRATEGY_PLAYBOOK: tuple[OptionsStrategyPlaybookItem, ...] = (
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.UNUSUAL_OPTIONS_FLOW,
        label="Unusual Options Flow",
        objective="Follow liquid call/put flow only when volume materially exceeds open interest.",
        setup=(
            "Volume/open-interest ratio >= 1",
            "Volume clears liquidity floor",
            "Spread is tradable",
        ),
        required_data=("option chain", "volume", "open interest", "bid", "ask"),
        risk_rules=(
            "Avoid illiquid contracts",
            "Size from premium at risk",
            "Prefer near-the-money",
        ),
        preferred_symbols=("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"),
        scanner_ready=True,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.OPENING_RANGE_BREAKOUT,
        label="Opening Range Breakout",
        objective="Trade calls above the opening range or puts below it after confirmation.",
        setup=(
            "First 15-30 minute range defined",
            "Break and hold outside range",
            "Volume confirms",
        ),
        required_data=("intraday bars", "volume", "option chain"),
        risk_rules=(
            "Stop inside opening range",
            "Target at least 2R",
            "No chase after extended move",
        ),
        preferred_symbols=("SPY", "QQQ", "IWM", "SPX"),
        scanner_ready=False,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.GAMMA_SQUEEZE,
        label="Gamma Squeeze",
        objective=(
            "Identify heavy near-dated call demand around key strikes "
            "with spot pushing toward them."
        ),
        setup=(
            "Call volume/OI expansion",
            "Spot near high-OI strike",
            "Bullish breakout or momentum",
        ),
        required_data=("option chain", "open interest by strike", "volume", "underlying trend"),
        risk_rules=("Use defined-risk calls or debit spreads", "Exit if spot rejects key strike"),
        preferred_symbols=("SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD"),
        scanner_ready=True,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.IV_CRUSH,
        label="IV Crush",
        objective="Sell premium after elevated implied volatility is likely to normalize.",
        setup=("IV elevated into event", "Event passes", "Premium remains rich"),
        required_data=("option chain", "implied volatility", "earnings calendar"),
        risk_rules=("Prefer defined-risk credit spreads", "Avoid naked short options"),
        preferred_symbols=("AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN"),
        scanner_ready=False,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.EARNINGS_MOMENTUM,
        label="Earnings Momentum",
        objective="Trade post-earnings continuation only after direction and liquidity confirm.",
        setup=(
            "Earnings gap with follow-through",
            "Volume above average",
            "Options spread tradable",
        ),
        required_data=("earnings calendar", "daily bars", "option chain", "volume"),
        risk_rules=(
            "Do not hold long premium through binary event unless planned",
            "Use defined stop",
        ),
        preferred_symbols=("AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL"),
        scanner_ready=False,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.WHEEL,
        label="Wheel Strategy",
        objective=(
            "Sell cash-secured puts and covered calls on liquid underlyings you are willing to own."
        ),
        setup=(
            "Bullish/neutral trend",
            "Put premium clears target yield",
            "Underlying acceptable for assignment",
        ),
        required_data=("option chain", "account buying power", "underlying price"),
        risk_rules=(
            "Cash-secured only",
            "Avoid assignment size above account limits",
            "No weak-trend symbols",
        ),
        preferred_symbols=("SPY", "QQQ", "AAPL", "MSFT", "NVDA"),
        scanner_ready=True,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.CREDIT_SPREAD_SCANNER,
        label="Credit Spread Scanner",
        objective="Find defined-risk premium sells with acceptable credit and distance from spot.",
        setup=(
            "Short strike out-of-the-money",
            "Credit justifies width",
            "Trend not against spread",
        ),
        required_data=("option chain", "bid", "ask", "strike ladder", "underlying trend"),
        risk_rules=("Defined risk only", "Credit/width threshold", "Stop or close before max loss"),
        preferred_symbols=("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA"),
        scanner_ready=True,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.DEBIT_SPREAD_SCANNER,
        label="Debit Spread Scanner",
        objective="Find directional defined-risk spreads with realistic target return.",
        setup=(
            "Directional trend confirmed",
            "Long strike near-the-money",
            "Target strike reachable",
        ),
        required_data=("option chain", "bid", "ask", "strike ladder", "underlying target"),
        risk_rules=("Debit paid is max loss", "Target at least 50% return", "Avoid wide spreads"),
        preferred_symbols=("SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "TSLA"),
        scanner_ready=True,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.ZERO_DTE_SPX,
        label="0DTE SPX Strategy",
        objective="Trade same-day index options only with strict R:R, liquidity, and stop rules.",
        setup=(
            "SPX/SPY/QQQ/IWM same-day expiry",
            "Opening range or momentum trigger",
            "Target >= 2R",
        ),
        required_data=("0DTE option chain", "intraday bars", "bid", "ask", "volume"),
        risk_rules=("Small premium budget", "Hard stop", "No averaging down", "Flat by close"),
        preferred_symbols=("SPX", "SPY", "QQQ", "IWM"),
        scanner_ready=False,
    ),
    OptionsStrategyPlaybookItem(
        key=OptionsStrategyKey.SPY_MOMENTUM,
        label="SPY Momentum",
        objective="Use SPY as the primary benchmark momentum engine for index-option direction.",
        setup=(
            "SPY trend and momentum align",
            "Short-term guard not negative",
            "Options liquidity strong",
        ),
        required_data=("SPY daily/intraday bars", "option chain", "volume", "open interest"),
        risk_rules=("Defined stop", "Prefer SPY/QQQ liquidity", "Skip chop/flat guard regime"),
        preferred_symbols=("SPY", "SPX", "QQQ"),
        scanner_ready=True,
    ),
)
