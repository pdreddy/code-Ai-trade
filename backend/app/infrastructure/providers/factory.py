"""Provider factory for configuration-driven market-data adapter selection."""

from typing import Protocol

from backend.app.domain.options import OptionsProvider
from backend.app.domain.providers import MarketDataProvider
from backend.app.infrastructure.providers.tradier_options import TradierOptionsProvider
from backend.app.infrastructure.providers.yahoo import YahooFinanceProvider
from backend.app.infrastructure.providers.yahoo_options import YahooOptionsProvider


class MarketDataProviderSettings(Protocol):
    """Settings subset required to choose a market-data provider."""

    @property
    def market_data_provider(self) -> str: ...


def create_market_data_provider(settings: MarketDataProviderSettings) -> MarketDataProvider:
    """Create the configured market-data provider adapter."""

    if settings.market_data_provider == "yahoo":
        return YahooFinanceProvider()
    raise ValueError(f"Unsupported market data provider: {settings.market_data_provider}")


class OptionsProviderSettings(Protocol):
    """Settings subset required to choose an options-data provider."""

    @property
    def options_data_provider(self) -> str: ...

    @property
    def tradier_api_token(self) -> str | None: ...

    @property
    def tradier_base_url(self) -> str: ...


def create_options_provider(settings: OptionsProviderSettings) -> OptionsProvider:
    """Create the configured options-data provider adapter.

    Defaults to Yahoo (no signup required, but its options endpoint blocks
    server IPs more aggressively than its chart endpoint). Set
    AI_QUANT_OPTIONS_DATA_PROVIDER=tradier plus AI_QUANT_TRADIER_API_TOKEN to
    use a Tradier developer-sandbox account instead — fails fast rather than
    silently falling back if the token is missing, since serving one
    provider's data while claiming to be another would be a lie about lineage.
    """

    if settings.options_data_provider == "yahoo":
        return YahooOptionsProvider()
    if settings.options_data_provider == "tradier":
        if not settings.tradier_api_token:
            raise ValueError(
                "AI_QUANT_OPTIONS_DATA_PROVIDER=tradier requires AI_QUANT_TRADIER_API_TOKEN"
            )
        return TradierOptionsProvider(
            api_token=settings.tradier_api_token, base_url=settings.tradier_base_url
        )
    raise ValueError(f"Unsupported options data provider: {settings.options_data_provider}")
