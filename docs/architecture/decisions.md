# Architecture Decisions

## Clean Architecture Boundary

Domain models and quantitative rules must not depend on FastAPI, SQLAlchemy, Celery, Redis, or frontend code. Application services coordinate use cases. Infrastructure adapters handle persistence, providers, queues, and external systems.

## Provider Configuration

Market data providers are selected by configuration. Version 1 supports Yahoo Finance. Future providers must implement the same provider contract so switching providers does not require application-service or UI changes.

## Backtest Execution Semantics

Backtests must generate signals on close and fill at the next open. Same-bar fills are disallowed to prevent look-ahead bias and future data leakage.

## Demo Mode

Demo mode may run real historical backtests and populate historical outputs. It must be clearly labeled as historical and must not fake live data.
