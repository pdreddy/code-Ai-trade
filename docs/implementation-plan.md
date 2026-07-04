# AI Quant Platform Implementation Plan

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
- Settings are centralized through Pydantic Settings with a `AI_QUANT_` environment prefix.
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
- `alembic.ini`, `backend/alembic/env.py`, and `backend/alembic/versions/0001_market_data_storage.py` for migration execution and initial market-data schema creation.
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
- Migration file tests for required tables and idempotency constraints.
- Repository integration tests against PostgreSQL.
- Data-quality regression tests for split and dividend scenarios.

## Milestone 5: AI Agent Framework

Objectives:

- Implement independent trend, momentum, volatility, risk, portfolio, mean-reversion, breakout, support/resistance, volume, and market-regime agents.
- Standardize agent outputs: BUY, SELL, HOLD, confidence, score, and reasons.
- Persist every agent vote for auditability and later model evaluation.

Files:

- `backend/app/domain/agents.py` for agent request, standardized vote, and agent protocol contracts.
- `backend/app/application/agents/technical.py` for deterministic V1 trend, momentum, volatility, risk, portfolio, mean-reversion, breakout, support/resistance, volume, and market-regime agents.
- `backend/app/application/agents/registry.py` for deterministic agent-set construction.
- `backend/app/infrastructure/repositories/signals.py` for later signal persistence.
- `tests/domain/test_agent_contracts.py` and `tests/domain/test_agents.py` for agent contract and deterministic vote coverage.

Architecture:

- Agents receive historical bars plus optional portfolio/risk context through typed inputs.
- Agents do not fetch data, mutate portfolios, place orders, or know API details.
- Reasons must be deterministic strings derived from evaluated conditions.

Dependencies:

- Pandas, NumPy, Scikit-learn, TA-Lib or pandas-ta, and optional LightGBM/XGBoost for later learned agents.

Acceptance criteria:

- Every required agent returns a complete auditable vote.
- Agent execution is deterministic for a fixed input dataset.
- Agents reject feature matrices with future data or insufficient history.

Testing:

- Unit tests proving the full required agent set is registered.
- Deterministic behavior tests using synthetic but internally consistent bar histories.
- Leakage tests validating agent requests reject future bars.

## Milestone 6: Master AI Decision Engine

Objectives:

- Combine agent votes into final action, confidence, risk score, stop loss, take profit, expected R multiple, and explanation.
- Persist every master decision with links back to source votes and input bar timestamp.
- Keep aggregation explainable and reproducible.

Files:

- `backend/app/application/decision_engine.py`.
- `backend/app/application/decision_service.py`.
- `tests/decisions/`.

Architecture:

- Decision policies are configuration driven and versioned.
- Decisions are generated after signal-bar close and cannot imply same-bar fills.
- The engine is stateless; repository writes are coordinated by an application service so aggregation remains pure and persistence remains explicit.

Dependencies:

- Domain agent contracts and signal repositories.

Acceptance criteria:

- Every decision references the exact agent votes used.
- Risk outputs are bounded and validated.
- Explanations include the dominant positive and negative drivers.

Testing:

- Unit tests for vote aggregation.
- Regression tests for conflicting agent scenarios.
- Service tests for decision persistence through the signal repository contract.

## Milestone 7: Event-Driven Backtester

Objectives:

- Implement a true event-driven backtest engine.
- Enforce signal-on-close and fill-on-next-open semantics.
- Compute CAGR, Sharpe, Sortino, Calmar, profit factor, win rate, trade count, max drawdown, exposure, benchmark returns, monthly returns, and trade lists.

Files:

- `backend/app/application/backtesting.py`.
- `tests/backtesting/`.
- Future persistence adapter: `backend/app/infrastructure/repositories/backtests.py`.

Architecture:

- Market, signal, order, fill, and portfolio events are emitted into an auditable event log.
- Execution simulation is isolated in the application layer so paper trading can reuse the same next-open fill semantics in a later milestone.
- The engine processes bars sequentially and only submits orders after the signal bar has closed.

Dependencies:

- Domain bars and master decisions from prior milestones.
- Pandas/NumPy/Polars and VectorBT remain optional future validation layers, not shortcuts around event semantics.

Acceptance criteria:

- Same-bar fills are impossible by design.
- Metrics match independent validation fixtures.
- Backtest requests are date-range driven, so 1, 3, 5, and 10 year ranges are supported by supplied bars.

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

- `backend/app/application/paper_trading.py`.
- `backend/app/application/execution.py`.
- `tests/paper_trading/`.

Architecture:

- Paper trading consumes market bars and pending orders through the same next-open execution model as backtesting.
- Broker state changes are auditable in memory for this milestone; persistence adapters remain future infrastructure work.
- Live broker adapters remain future infrastructure additions.

Dependencies:

- Shared execution model, domain orders/trades/portfolio entities, and risk engine.
- Execution repositories, market data repositories, and Redis/Celery remain later asynchronous workflow dependencies.

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

- `backend/app/application/risk.py`.
- `tests/risk/`.
- Future persistence adapter for risk decisions.

Architecture:

- Risk checks are pure policies over portfolio, order, market, and configuration inputs.
- Risk decisions are explicit approve/reject outputs with auditable reasons.
- Kill-switch state is supplied through the domain risk rule and can be centralized by future persistence/configuration adapters.

Dependencies:

- Domain risk rules, portfolio/order context, liquidity inputs, and configuration policies.

Acceptance criteria:

- Orders breaching any configured limit cannot reach execution.
- Risk rejections include explicit human-readable reasons; machine-readable reason codes can be added with persistence/API adapters.
- Risk policies can run in historical and paper contexts.

Testing:

- Unit tests for every risk policy.
- Scenario tests for exposure, liquidity, drawdown, and correlation constraints.
- Regression tests for kill-switch behavior.

## Milestone 10: Frontend Research Terminal

Objectives:

- Build Dashboard, Signals, Stock Details, Backtests, Paper Trades, Portfolio, Analytics, and Watchlists pages backed by available real research APIs, with honest unavailable states when providers fail.
- Keep business logic outside UI components.
- Provide a professional dark terminal UX inspired by Bloomberg, TradingView, ThinkOrSwim, and Interactive Brokers.

Files:

- `frontend/app/` route segments.
- `frontend/components/` reusable terminal widgets.
- `frontend/lib/platform-data.ts` static capability metadata.
- Future API clients/query hooks once backend endpoints are available.

Architecture:

- UI components render typed data and emit typed intents; they do not implement trading rules.
- Route components compose reusable terminal shell/panel widgets and avoid business logic.
- Demo mode labeling will be controlled by backend state once API endpoints exist.

Dependencies:

- Next.js 15, React 19, and TailwindCSS for the current terminal shell.
- shadcn/ui, TanStack Query/Table, Framer Motion, Lightweight Charts, Recharts, React Hook Form, and Zod remain planned for data-connected workflows.

Acceptance criteria:

- No dead controls are shipped; controls either execute real flows or are absent.
- Pages are responsive and keyboard-accessible.
- Dashboard, stock details, backtests, paper trades, portfolio, analytics, and signals render the $10,000 provider-backed research report when the backend is reachable.
- Unusual-options UI is explicitly labeled as an underlying-driven watch plan until a real options-chain provider and execution adapter exist.

Testing:

- Type checks and production build.
- Component tests where practical.
- API contract tests against backend schemas.

## Milestone 11: Analytics and Reporting

Objectives:

- Add equity curves, drawdowns, benchmark analysis, monthly returns, trade analytics, portfolio reporting, and daily paper research rollups.
- Support institutional research review workflows.
- Provide exportable analytics without compromising source-of-truth storage.

Files:

- `backend/app/application/analytics.py`.
- `backend/app/api/v1/analytics.py`.
- `tests/analytics/`.
- `tests/api/test_capabilities_and_analytics.py`.

Architecture:

- Analytics are derived from real backtest, trade, and portfolio records supplied by persistence adapters or API callers.
- Calculations are deterministic and versionable.
- Chart and report DTOs are prepared by backend services rather than computed in UI components.
- The daily research report uses a $10,000 paper-capital default with equal symbol sleeves and signal-on-close/fill-next-open semantics.

Dependencies:

- Existing backtest, trade, and portfolio entities.
- Pandas/NumPy/Polars, Plotly, Recharts, and Lightweight Charts remain optional future visualization/validation layers.

Acceptance criteria:

- Metrics reconcile with backtester outputs.
- Equity and drawdown chart DTOs are generated from actual result curves.
- Reports can be regenerated from persisted inputs once persistence adapters are added.

Testing:

- Unit tests for metrics and chart DTOs.
- API tests for caller-supplied trade analytics.
- Future frontend rendering checks for chart DTOs.

## Milestone 12: Production Hardening

Objectives:

- Add API discovery endpoints, analytics API, execution/risk persistence adapters, CI/CD, production runbook, security baseline, and observability guidance.
- Keep Docker Compose and Render deployment flows aligned with renamed platform configuration.
- Define operational runbooks for deployment, health checks, backups, and future data/trading workflows.

Files:

- `.github/workflows/quality.yml`.
- `docs/operations/production-hardening.md`.
- `backend/app/api/v1/capabilities.py`.
- `backend/app/api/v1/analytics.py`.
- `backend/app/infrastructure/repositories/execution.py`.
- `backend/alembic/versions/0002_execution_and_risk_audit.py`.
- Render, Docker Compose, and configuration files renamed away from prior project branding.

Architecture:

- API endpoints expose readiness/capability state and caller-supplied analytics without fabricating trading data.
- Paper orders, paper trades, and risk decisions have audit persistence adapters and migration coverage.
- Secrets stay in environment/configuration boundaries.
- Database migrations and backups are explicit release steps in the runbook.

Dependencies:

- GitHub Actions, Docker/Render deployment configuration, PostgreSQL managed backups, and future observability libraries.

Acceptance criteria:

- CI runs backend and frontend quality gates.
- Capability and analytics endpoints are covered by API tests where FastAPI is installed.
- Execution/risk audit tables are covered by migration and model tests.
- Deployment and operations docs are sufficient for a new engineer to prepare cloud deployment and production checks.

Testing:

- Local execution of CI-equivalent commands.
- API tests for production capability endpoints and analytics summary endpoint.
- Migration/model tests for paper order, paper trade, and risk decision audit tables.
- Future Docker Compose smoke tests and backup/restore rehearsal tests.
