# Alternative Market Data Provider Roadmap

Yahoo Finance is acceptable for early OHLCV research, but it is not sufficient for institutional daily 0DTE research, unusual options flow, news/event trading, or auditable execution simulation. The platform should keep Yahoo as a low-cost fallback and add specialized providers through the existing provider abstraction.

## Recommended provider stack

| Need | Recommended candidates | Why |
| --- | --- | --- |
| Institutional OPRA/equity options and exchange-grade history | Databento | Databento advertises real-time and historical market data for equities and equity options, with OPRA/reference data coverage suitable for institutional research. https://databento.com/options |
| Fast options-chain + brokerage path | Tradier | Tradier exposes option chains for an underlying and expiration, including Greek and IV data courtesy of ORATS, plus brokerage APIs for future routing. https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains |
| Developer-friendly equities/options/brokerage | Alpaca | Alpaca documents historical option data and a combined market-data/brokerage ecosystem. It is useful for faster integration, but historical options availability must be checked against the strategy horizon. https://docs.alpaca.markets/us/docs/historical-option-data |
| Options analytics and unusual activity | Intrinio | Intrinio documents realtime option chains with NBBO, latest trades, Greeks, implied volatility, and unusual activity. https://docs.intrinio.com/documentation/web_api/get_options_chain_realtime_v2 |
| Broad stocks/options/news ecosystem | Massive / Polygon | Massive documents options APIs for trades, quotes, candlesticks, Greeks, IV, WebSockets, REST, and flat files. https://massive.com/options |
| News catalysts | Benzinga | Benzinga documents news, market, and company-data APIs and markets real-time headlines/news coverage. https://docs.benzinga.com/introduction/welcome |
| Company news, sentiment, fundamentals | Finnhub | Finnhub documents company news and broader APIs for fundamentals, sentiment, and alternative data. https://finnhub.io/docs/api/company-news |

## Integration sequence

1. Add an `OptionsDataProvider` protocol for expirations, chains, quotes, trades, Greeks, IV, open interest, and volume.
2. Add a `NewsCatalystProvider` protocol for ticker-tagged headlines, event timestamps, sentiment, and source lineage.
3. Implement one options provider first: Tradier for fastest brokerage-adjacent integration or Databento for institutional OPRA-grade data.
4. Implement one news provider next: Benzinga for day-trading catalysts or Finnhub for broader sentiment/fundamental enrichment.
5. Only then upgrade 0DTE rows from intent plans to paper option fills.

## Non-negotiable 0DTE execution checks

Before any daily 0DTE paper fill is shown as executed, the runtime must verify:

- The requested underlying has a listed expiration for the same session.
- The selected strike exists for that expiration.
- Bid/ask, last trade, volume, and open interest are present.
- Greeks and IV are present or can be computed from trusted inputs.
- News/unusual-flow timestamps are not after the signal timestamp.
- The simulator uses signal-on-close and next-session/next-event fill semantics without look-ahead leakage.

Small- and mid-cap names must not be assumed to support daily 0DTE. The provider must confirm the expiration calendar and tradable contract universe for every symbol/date.
