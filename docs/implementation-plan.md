# KOC3 Quant Platform Implementation Plan

This repository will be built incrementally. Each milestone must compile, run, and pass its acceptance checks before the next milestone begins. Milestones are intentionally narrow so the platform can grow without weakening data-quality, backtest, or execution guarantees.

## Milestone 1: Foundation

Objectives:

- Establish `/backend`, `/frontend`, `/docker`, `/docs`, `/scripts`, `/tests`, and `/config` boundaries.
- Provide typed FastAPI application factory and health endpoint.
- Provide Next.js 15 shell with terminal design language.
- Provide Docker Compose for PostgreSQL, Redis, backend, and frontend.
- Provide lint, type-check, and test tooling.

Files:

- `backend/app/main.py`, `backend/app/api/v1/health.py`, and `backend/app/core/config.py` define the API factory, system endpoint, and typed runtime settings.
- `frontend/app/page.tsx`, `frontend/app/layout.tsx`, `frontend/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, and `frontend/.eslintrc.json` define the terminal shell and frontend quality boundary.
- `docker-compose.yml`, `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`, `config/local.env.example`, `pyproject.toml`, and `scripts/check-backend.sh` define local runtime and quality automation.
- `tests/api/test_health.py` validates the public backend health contract.

Architecture:

- FastAPI is created through an application factory so tests, workers, and future deployment entrypoints can inject settings.
- Settings are centralized through Pydantic Settings with a `KOC3_` environment prefix.
- The frontend shell is a typed Next.js app-router application with a dark terminal visual system and no business logic.
- Docker Compose starts PostgreSQL and Redis before application services by using container health checks.

Dependencies:

- Python 3.12 with FastAPI, Pydantic v2, SQLAlchemy 2-compatible database drivers, Redis, Celery, pytest, ruff, and mypy.
- Node 22 with Next.js 15, React 19, TypeScript, TailwindCSS, and the UI/data libraries reserved for later milestones.

Acceptance criteria:

- Backend health endpoint returns runtime metadata.
- Frontend shell builds from typed Next.js sources.
- Docker Compose declares database/cache/application services.
- No trading logic, fake data, or dead controls are introduced.

Testing:

- `ruff check .`
- `mypy backend tests`
- `pytest`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Milestone 2: Backend Domain Core

Objectives:

- Add framework-independent domain entities for instruments, OHLCV bars, corporate actions, agent signals, master decisions, orders, trades, portfolios, risk rules, and backtest runs.
- Encode invariants that protect against malformed market data, unauditable decisions, invalid order states, and impossible backtest requests before data reaches persistence or APIs.
- Define repository contracts as protocols so application services can depend on abstractions rather than SQLAlchemy, Redis, Celery, or provider SDKs.

Files:

- `backend/app/domain/enums.py` for shared enum vocabulary.
- `backend/app/domain/errors.py` for domain-specific validation errors.
- `backend/app/domain/value_objects.py` for immutable price, quantity, confidence, and risk fraction types.
- `backend/app/domain/entities.py` for core research, portfolio, execution, and backtest entities.
- `backend/app/domain/repositories.py` for persistence contracts.
- `tests/domain/test_domain_entities.py` for pure unit coverage of invariant behavior.

Architecture:

- Domain code must import only Python standard-library modules and other domain modules.
- Entities are immutable dataclasses with slot allocation to reduce accidental mutation and memory overhead in research workloads.
- Money, quantity, confidence, risk, commission, and slippage values use `Decimal` to avoid binary floating-point drift in accounting boundaries.
- Repository protocols form the clean-architecture seam that later infrastructure adapters must implement.

Dependencies:

- Python standard library only for domain code.
- Pytest for domain unit tests.

Acceptance criteria:

- Domain entities can be imported without FastAPI, SQLAlchemy, Redis, Celery, or provider libraries.
- Invalid OHLCV bars, invalid order states, unauditable signals, invalid backtest ranges, and impossible trade exits fail fast.
- Portfolio equity and PnL calculations are deterministic and Decimal-based.
- Repository interfaces expose contracts without implementation leakage.

Testing:

- `ruff check backend/app/domain tests/domain`
- `mypy backend/app/domain tests/domain`
- `pytest tests/domain`

## Milestone 3: Data Provider Layer

Objectives:

- Introduce a market data provider abstraction selected by configuration.
- Implement Yahoo Finance as the V1 provider without coupling application services to Yahoo-specific response formats.
- Normalize raw provider output into domain-safe bars, corporate actions, and provider lineage metadata.

Files:

- `backend/app/application/market_data.py` for provider-backed market-data use cases.
- `backend/app/domain/providers.py` for provider contracts, historical-data requests, normalized responses, and provider lineage.
- `backend/app/infrastructure/providers/yahoo.py` for Yahoo Finance chart adapter code.
- `backend/app/infrastructure/providers/factory.py` for configuration-driven provider selection.
- `tests/providers/` for provider normalization, corporate-action parsing, error handling, and provider-factory coverage.

Architecture:

- Provider adapters return normalized domain bars, corporate actions, and explicit quality metadata; they do not persist data directly.
- Configuration chooses the provider through a factory; switching providers cannot require service-layer or UI changes.
- Provider timestamps are normalized to timezone-aware UTC datetimes at the boundary.

Dependencies:

- Standard-library HTTP/JSON parsing for the initial Yahoo chart adapter to avoid unnecessary runtime dependencies.
- Pandas or Polars may be introduced later only where it improves parsing correctness or performance.

Acceptance criteria:

- SPY, QQQ, IWM, DIA, S&P 500 constituents, Nasdaq stocks, and future ticker symbols share one provider contract.
- Corporate actions are retrieved or represented with source lineage.
- Provider failures return actionable application errors without corrupting storage.

Testing:

- Unit tests for request validation, normalization, and error mapping.
- Deterministic provider-response tests for bars, adjusted close, dividends, and splits.
- Factory tests proving provider selection remains configuration driven.

## Milestone 4: Market Data Storage

Objectives:

- Add SQLAlchemy 2 models and migrations for instruments, bars, corporate actions, ingestion batches, and quality checks.
- Persist provider lineage and adjustment policy for reproducible research.
- Add an analytical export boundary for Parquet/Arrow datasets.

Files:

- `backend/app/infrastructure/database/models.py` for SQLAlchemy instrument, bar, corporate-action, ingestion-batch, and quality-check tables.
- `backend/app/infrastructure/database/session.py` for engine, session factory, and transactional session scope construction.
- `backend/app/infrastructure/repositories/market_data.py` for SQLAlchemy market-data persistence and retrieval mappings.
- `backend/alembic/` migrations.
- `tests/storage/` and `tests/integration/database/` for schema and repository coverage.

Architecture:

- SQLAlchemy models stay in infrastructure and never leak into domain entities.
- Ingestion writes are idempotent by provider, symbol, timestamp, and adjustment policy.
- Parquet export is a read-optimized boundary, not the system of record.

Dependencies:

- PostgreSQL, SQLAlchemy 2, Alembic, psycopg, PyArrow, and optional Polars.

Acceptance criteria:

- Duplicate bars cannot silently create duplicate time-series records because uniqueness includes instrument, timestamp, provider, and adjustment policy.
- Corporate actions are versioned with source lineage.
- Storage supports adjusted and raw data policies without ambiguity.

Testing:

- Schema tests for idempotency constraints.
- Migration tests.
- Repository integration tests against PostgreSQL.
- Data-quality regression tests for split and dividend scenarios.

## Milestone 5: AI Agent Framework

Objectives:

- Implement independent trend, momentum, volatility, risk, portfolio, mean-reversion, breakout, support/resistance, volume, and market-regime agents.
- Standardize agent outputs: BUY, SELL, HOLD, confidence, score, and reasons.
- Persist every agent vote for auditability and later model evaluation.

Files:

- `backend/app/domain/agents.py`.
- `backend/app/application/agents/`.
- `backend/app/infrastructure/repositories/signals.py`.
- `tests/agents/`.

Architecture:

- Agents receive historical features and portfolio context through typed inputs.
- Agents do not fetch data, mutate portfolios, place orders, or know API details.
- Reasons must be deterministic strings derived from evaluated conditions.

Dependencies:

- Pandas, NumPy, Scikit-learn, TA-Lib or pandas-ta, and optional LightGBM/XGBoost for later learned agents.

Acceptance criteria:

- Every required agent returns a complete auditable vote.
- Agent execution is deterministic for a fixed input dataset.
- Agents reject feature matrices with future data or insufficient history.

Testing:

- Unit tests per agent.
- Regression tests using known historical windows.
- Leakage tests validating feature cutoffs.

## Milestone 6: Master AI Decision Engine

Objectives:

- Combine agent votes into final action, confidence, risk score, stop loss, take profit, expected R multiple, and explanation.
- Persist every master decision with links back to source votes and input bar timestamp.
- Keep aggregation explainable and reproducible.

Files:

- `backend/app/application/decision_engine.py`.
- `backend/app/domain/decisions.py` if specialized decision policies are needed.
- `tests/decisions/`.

Architecture:

- Decision policies are configuration driven and versioned.
- Decisions are generated after signal-bar close and cannot imply same-bar fills.
- The engine is stateless except for repository writes.

Dependencies:

- Domain agent contracts and signal repositories.

Acceptance criteria:

- Every decision references the exact agent votes used.
- Risk outputs are bounded and validated.
- Explanations include the dominant positive and negative drivers.

Testing:

- Unit tests for vote aggregation.
- Regression tests for conflicting agent scenarios.
- Persistence tests for decision lineage.

## Milestone 7: Event-Driven Backtester

Objectives:

- Implement a true event-driven backtest engine.
- Enforce signal-on-close and fill-on-next-open semantics.
- Compute CAGR, Sharpe, Sortino, Calmar, profit factor, win rate, trade count, max drawdown, exposure, benchmark returns, monthly returns, and trade lists.

Files:

- `backend/app/domain/backtesting.py`.
- `backend/app/application/backtesting/`.
- `backend/app/infrastructure/repositories/backtests.py`.
- `tests/backtesting/`.

Architecture:

- Market events, signal events, order events, fill events, and portfolio events are explicit.
- Execution simulation is shared with paper trading to avoid semantic drift.
- The engine cannot read bars later than the event being processed.

Dependencies:

- Pandas/NumPy or Polars for metrics and time-series calculations.
- VectorBT may be used for validation or analytics, not as a shortcut around event semantics.

Acceptance criteria:

- Same-bar fills are impossible by design.
- Metrics match independent validation fixtures.
- Backtests support 1, 3, 5, and 10 year ranges.

Testing:

- Unit tests for event sequencing.
- Regression tests for known trade lists.
- Backtest validation tests for no look-ahead leakage.

## Milestone 8: Paper Trading

Objectives:

- Implement a paper broker with pending, filled, cancelled, and rejected order states.
- Reuse the same execution semantics as the backtester.
- Track orders, fills, trades, positions, and cash without live brokerage integration.

Files:

- `backend/app/application/paper_trading/`.
- `backend/app/domain/execution.py` if additional execution policies are needed.
- `tests/paper_trading/`.

Architecture:

- Paper trading consumes market events and orders through the same fill engine as backtesting.
- Broker state changes are auditable and persisted.
- Live broker adapters remain future infrastructure additions.

Dependencies:

- Execution repositories, market data repositories, and Redis/Celery for later asynchronous workflows.

Acceptance criteria:

- Paper fills match backtest fills for identical event streams.
- Invalid orders are rejected with explicit reasons.
- Order state transitions are deterministic and valid.

Testing:

- Unit tests for state transitions.
- Integration tests comparing backtest and paper fill outputs.
- API tests for paper order submission once endpoints are added.

## Milestone 9: Risk Engine

Objectives:

- Enforce maximum risk per trade, maximum exposure, maximum sector exposure, maximum drawdown, kill switch, liquidity filter, and correlation filter.
- Make risk checks reusable across backtesting, paper trading, and future live trading.
- Persist risk decisions and rejection reasons.

Files:

- `backend/app/domain/risk.py`.
- `backend/app/application/risk/`.
- `tests/risk/`.

Architecture:

- Risk checks are pure policies over portfolio, order, market, and configuration inputs.
- Risk decisions are explicit allow/reject/reduce outputs.
- Kill-switch state is centralized and observable.

Dependencies:

- Portfolio repositories, market data repositories, and configuration policies.

Acceptance criteria:

- Orders breaching any configured limit cannot reach execution.
- Risk rejections include machine-readable codes and human-readable explanations.
- Risk policies can run in historical and paper contexts.

Testing:

- Unit tests for every risk policy.
- Scenario tests for exposure, liquidity, drawdown, and correlation constraints.
- Regression tests for kill-switch behavior.

## Milestone 10: Frontend Research Terminal

Objectives:

- Build Dashboard, Scanner, Signals, Stock Details, Backtests, Trades, Portfolio, Analytics, Strategies, Watchlists, and Settings pages.
- Keep business logic outside UI components.
- Provide a professional dark terminal UX inspired by Bloomberg, TradingView, ThinkOrSwim, and Interactive Brokers.

Files:

- `frontend/app/` route segments.
- `frontend/components/` reusable terminal widgets.
- `frontend/lib/api/` typed API clients.
- `frontend/lib/query/` TanStack Query hooks.
- `frontend/types/` frontend DTOs.

Architecture:

- UI components render typed data and emit typed intents; they do not implement trading rules.
- API clients isolate transport concerns.
- Demo mode labeling is controlled by backend state and surfaced consistently.

Dependencies:

- Next.js 15, React 19, TailwindCSS, shadcn/ui, TanStack Query/Table, Framer Motion, Lightweight Charts, Recharts, React Hook Form, and Zod.

Acceptance criteria:

- No dead controls are shipped; controls either execute real flows or are absent.
- Pages are responsive and keyboard-accessible.
- Stock details and backtest screens render only real backend data or clearly labeled historical demo outputs.

Testing:

- Type checks and production build.
- Component tests where practical.
- API contract tests against backend schemas.

## Milestone 11: Analytics and Reporting

Objectives:

- Add equity curves, drawdowns, benchmark analysis, monthly returns, trade analytics, and portfolio reporting.
- Support institutional research review workflows.
- Provide exportable analytics without compromising source-of-truth storage.

Files:

- `backend/app/application/analytics/`.
- `backend/app/domain/analytics.py`.
- `frontend/components/charts/`.
- `tests/analytics/`.

Architecture:

- Analytics are derived from persisted backtest, trade, market, and portfolio records.
- Calculations are deterministic and versionable.
- Chart components consume prepared DTOs rather than computing research metrics in the UI.

Dependencies:

- Pandas/NumPy/Polars, Plotly for backend figure generation where needed, Recharts/Lightweight Charts for frontend rendering.

Acceptance criteria:

- Metrics reconcile with backtester outputs.
- Benchmark comparisons use aligned calendars and explicit missing-data handling.
- Reports can be regenerated from persisted inputs.

Testing:

- Unit tests for metrics.
- Regression tests against known monthly return and drawdown fixtures.
- Frontend rendering checks for chart DTOs.

## Milestone 12: Production Hardening

Objectives:

- Add observability, security, CI/CD, backup/restore, deployment docs, and performance profiling.
- Prepare Docker Compose flows for future cloud deployment.
- Define operational runbooks for data ingestion, backtesting, paper trading, and recovery.

Files:

- `.github/workflows/` or equivalent CI configuration.
- `docs/operations/`.
- `backend/app/core/observability.py`.
- `docker/` production-oriented Docker assets.
- `scripts/` operational commands.

Architecture:

- Application services emit structured logs and metrics.
- Secrets stay in environment/configuration boundaries.
- Database migrations and backups are explicit release steps.

Dependencies:

- CI runner, Docker BuildKit, PostgreSQL backup tooling, and observability libraries selected during implementation.

Acceptance criteria:

- CI runs backend and frontend quality gates.
- Deployment docs are sufficient for a new engineer to run the platform locally and prepare a cloud deployment.
- Operational scripts fail fast and are safe to rerun.

Testing:

- CI dry-runs where available.
- Docker Compose smoke tests.
- Backup/restore rehearsal tests.
