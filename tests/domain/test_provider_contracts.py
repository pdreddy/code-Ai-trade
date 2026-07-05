from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.app.domain.errors import DomainValidationError
from backend.app.domain.providers import (
    NewsCatalyst,
    NewsCatalystRequest,
    OptionChainRequest,
    OptionContract,
    OptionQuote,
)


def test_option_chain_request_rejects_expired_chain() -> None:
    with pytest.raises(DomainValidationError):
        OptionChainRequest(
            symbol="SPY",
            expiration=date(2026, 1, 1),
            as_of=datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_option_quote_requires_valid_market_and_liquidity_fields() -> None:
    contract = OptionContract(
        symbol="SPY260105C00500000",
        underlying_symbol="SPY",
        expiration=date(2026, 1, 5),
        strike=Decimal("500"),
        right="CALL",
    )

    with pytest.raises(DomainValidationError):
        OptionQuote(
            contract=contract,
            bid=Decimal("2"),
            ask=Decimal("1"),
            last=Decimal("1.5"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal("0.20"),
            delta=Decimal("0.50"),
            gamma=Decimal("0.05"),
            theta=Decimal("-0.10"),
            vega=Decimal("0.12"),
            quoted_at=datetime(2026, 1, 5, 15, 30, tzinfo=UTC),
        )


def test_news_catalyst_request_rejects_future_leakage_window_errors() -> None:
    now = datetime(2026, 1, 5, 15, 30, tzinfo=UTC)

    with pytest.raises(DomainValidationError):
        NewsCatalystRequest(symbols=("SPY",), start=now, end=now - timedelta(minutes=1))


def test_news_catalyst_requires_source_headline_and_symbol() -> None:
    with pytest.raises(DomainValidationError):
        NewsCatalyst(
            symbol="SPY",
            headline=" ",
            source="provider",
            published_at=datetime(2026, 1, 5, 15, 30, tzinfo=UTC),
            url=None,
            sentiment_score=None,
            relevance_score=None,
        )
