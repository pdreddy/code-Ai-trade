# KOC3 Quant Platform Implementation Plan

This repository will be built incrementally. Each milestone must compile, run, and pass its acceptance checks before the next milestone begins.

## Milestone 1: Foundation

- Establish `/backend`, `/frontend`, `/docker`, `/docs`, `/scripts`, `/tests`, and `/config` boundaries.
- Provide typed FastAPI application factory and health endpoint.
- Provide Next.js 15 shell with terminal design language.
- Provide Docker Compose for PostgreSQL, Redis, backend, and frontend.
- Provide lint, type-check, and test tooling.

Acceptance criteria:

- Backend health endpoint returns runtime metadata.
- Frontend shell builds from typed Next.js sources.
- Docker Compose declares database/cache/application services.
- No trading logic, fake data, or dead controls are introduced.

## Milestone 2: Backend Domain Core

- Add domain models for instruments, bars, corporate actions, signals, decisions, orders, trades, portfolios, risk rules, and backtests.
- Keep domain code independent of FastAPI and SQLAlchemy.
- Define repository interfaces and service-layer use cases.

## Milestone 3: Data Provider Layer

- Implement provider abstraction with Yahoo Finance V1.
- Normalize OHLCV and corporate action data.
- Persist provider lineage and adjustment policy.

## Milestone 4: Market Data Storage

- Add SQLAlchemy 2 models and Alembic migrations.
- Store instruments, bars, corporate actions, ingestion batches, and quality checks.
- Add Parquet/Arrow analytical export boundary.

## Milestone 5: AI Agent Framework

- Implement independent trend, momentum, volatility, risk, portfolio, mean reversion, breakout, support/resistance, volume, and market-regime agents.
- Persist agent votes with reasons, confidence, and scores.

## Milestone 6: Master AI Decision Engine

- Combine agent decisions into a final action, confidence, risk score, stop loss, take profit, expected R multiple, and explanation.
- Persist every decision for reproducibility.

## Milestone 7: Event-Driven Backtester

- Enforce signal-on-close and fill-on-next-open execution.
- Compute institutional metrics, benchmark comparisons, monthly returns, and trade lists.

## Milestone 8: Paper Trading

- Implement paper broker with order states and execution semantics identical to the backtester.

## Milestone 9: Risk Engine

- Enforce risk per trade, exposure, sector exposure, drawdown, kill switch, liquidity, and correlation constraints.

## Milestone 10: Frontend Research Terminal

- Build Dashboard, Scanner, Signals, Stock Details, Backtests, Trades, Portfolio, Analytics, Strategies, Watchlists, and Settings pages.
- Keep business logic outside UI components.

## Milestone 11: Analytics and Reporting

- Add equity curves, drawdowns, benchmark analysis, trade analytics, and portfolio reporting.

## Milestone 12: Production Hardening

- Add observability, security, CI/CD, backup/restore, deployment docs, and performance profiling.
