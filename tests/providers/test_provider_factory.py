from dataclasses import dataclass

from backend.app.infrastructure.providers import YahooFinanceProvider, create_market_data_provider


@dataclass(frozen=True, slots=True)
class _Settings:
    market_data_provider: str


def test_provider_factory_uses_configured_yahoo_provider() -> None:
    settings = _Settings(market_data_provider="yahoo")

    provider = create_market_data_provider(settings)

    assert isinstance(provider, YahooFinanceProvider)
