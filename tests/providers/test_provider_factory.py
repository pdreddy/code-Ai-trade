from dataclasses import dataclass

import pytest

from backend.app.infrastructure.providers import (
    MassiveOptionsProvider,
    TradierOptionsProvider,
    YahooFinanceProvider,
    YahooOptionsProvider,
    create_market_data_provider,
    create_options_provider,
)


@dataclass(frozen=True, slots=True)
class _Settings:
    market_data_provider: str


def test_provider_factory_uses_configured_yahoo_provider() -> None:
    settings = _Settings(market_data_provider="yahoo")

    provider = create_market_data_provider(settings)

    assert isinstance(provider, YahooFinanceProvider)


@dataclass(frozen=True, slots=True)
class _OptionsSettings:
    options_data_provider: str
    tradier_api_token: str | None = None
    tradier_base_url: str = "https://sandbox.tradier.com/v1"
    massive_api_key: str | None = None
    massive_base_url: str = "https://api.massive.com"


def test_options_provider_factory_defaults_to_yahoo() -> None:
    provider = create_options_provider(_OptionsSettings(options_data_provider="yahoo"))

    assert isinstance(provider, YahooOptionsProvider)


def test_options_provider_factory_builds_tradier_when_token_present() -> None:
    provider = create_options_provider(
        _OptionsSettings(options_data_provider="tradier", tradier_api_token="secret")
    )

    assert isinstance(provider, TradierOptionsProvider)


def test_options_provider_factory_builds_massive_when_key_present() -> None:
    provider = create_options_provider(
        _OptionsSettings(options_data_provider="massive", massive_api_key="secret")
    )

    assert isinstance(provider, MassiveOptionsProvider)


def test_options_provider_factory_fails_fast_without_a_massive_key() -> None:
    with pytest.raises(ValueError, match="MASSIVE_API_KEY"):
        create_options_provider(_OptionsSettings(options_data_provider="massive"))


def test_options_provider_factory_fails_fast_without_a_tradier_token() -> None:
    with pytest.raises(ValueError, match="TRADIER_API_TOKEN"):
        create_options_provider(_OptionsSettings(options_data_provider="tradier"))


def test_options_provider_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        create_options_provider(_OptionsSettings(options_data_provider="bloomberg"))
