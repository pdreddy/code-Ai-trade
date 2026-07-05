# AI Quant Platform

Production-grade foundation for an AI quantitative research and trading platform.

## Milestone Status

Milestone 1 establishes the repository architecture, typed FastAPI service, Next.js 15 terminal shell, Docker Compose services, and baseline quality tooling. Trading, data-provider, agent, and backtest logic are intentionally deferred to later milestones so each layer can be implemented correctly.

## Repository Layout

```text
backend/   FastAPI application and backend architecture
frontend/  Next.js terminal UI
docker/    Container build files
docs/      Architecture and implementation documentation
scripts/   Operational scripts
config/    Environment configuration examples
tests/     Backend automated tests
```

## Docker Compose

The Compose project is explicitly named `ai-quant-platform` so local containers and volumes do not reuse old project-specific database volumes from this repository path. If you previously started the old stack, stop it before starting the renamed stack:

```bash
docker compose -p code-ai-trade down
docker compose up --build
```

## Local Backend

```bash
python -m pip install -e .[dev]
uvicorn backend.app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

## Local Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose

Run Compose commands from the repository root, where `docker-compose.yml` lives. If your shell prompt is inside `frontend/`, move back to the repo root first:

```bash
cd ..
```

```bash
docker compose up --build
```

Alternatively, from inside `frontend/`, point Docker Compose at the root Compose file explicitly:

```bash
docker compose -f ../docker-compose.yml up --build
```

Services:

- Backend API: <http://localhost:8000>
- Frontend: <http://localhost:3000>
- PostgreSQL: `localhost:${AI_QUANT_POSTGRES_PORT:-15432}`
- Redis: `localhost:${AI_QUANT_REDIS_PORT:-16379}`

The Postgres and Redis host ports intentionally default to `15432` and `16379` to avoid collisions with locally installed database services. Override them when needed:

```bash
AI_QUANT_POSTGRES_PORT=5432 AI_QUANT_REDIS_PORT=6379 docker compose up --build
```

## Quality Checks

```bash
ruff check .
mypy backend tests
pytest
cd frontend && npm run typecheck
cd frontend && npm run build
```

## Five-Year Market Snapshot

The UI does not show synthetic prices. To populate the Watchlists page with real five-year Yahoo Finance chart data for SPY, QQQ, IWM, and DIA, run:

```bash
python scripts/generate_market_snapshot.py
cd frontend && npm run build
```

If you are running with Docker Compose, run the snapshot generator from the repo root and then rebuild/restart the frontend container:

```bash
docker compose run --rm market-snapshot
docker compose up -d --build frontend
```

The script writes `frontend/lib/generated-market-snapshot.ts`, which is intentionally empty until regenerated from a real provider response.


## Alternative Data Feeds

Yahoo Finance remains the fallback OHLCV provider. For daily 0DTE options, small/mid-cap option eligibility, news catalysts, and unusual options flow, use the provider roadmap in `docs/data-provider-roadmap.md`. The backend also exposes vetted candidates at:

```bash
curl "http://localhost:8000/api/v1/platform/data-provider-candidates"
```

## $10,000 Daily Paper Research Report

The active UI research workspaces call the backend daily report endpoint with `$10,000` of paper capital and real five-year Yahoo Finance OHLCV bars. The UI now accepts comma-separated symbols, so you can run the report for ETFs, large caps, mid caps, small caps, or event/news tickers when Yahoo provides enough OHLCV history. The report simulates entries and exits with the platform rule `signal on close, fill on next open`; it does not send live broker orders.

```bash
curl "http://localhost:8000/api/v1/research/daily-report?capital=10000"
```

The response includes next-session paper candidates, all generated daywise strategy trades for the covered period, portfolio-level equity/return/win-rate metrics, an underlying-driven unusual-options watch plan, and explicit 0DTE CALL/PUT paper intents for the requested symbols. The 0DTE rows are not options executions: they use the latest underlying signal to create same-expiration option intent plans while requiring a real options-chain provider for premium, bid/ask liquidity, Greeks, IV, open interest, volume, and fills before any paper options workflow can execute.

## Institutional Research Additions

The daily report now includes additive institutional analytics fields without changing the endpoint path:

- Portfolio summary metrics: cash, invested capital, today PnL, annualized return, Sharpe, Sortino, Calmar, profit factor, expectancy, average winner/loser, drawdown, and risk score.
- Per-symbol backtest metrics: equity curve, drawdown, exposure, volatility, alpha/beta placeholders derived from available benchmark context, information ratio, tracking error, recovery time, Omega, MAR, and streak statistics.
- Professional trade journal fields: trade ID, direction, holding period, position size, entry/exit signal, strategy, regime, confidence, risk/reward, stop, target, gross/net PnL, costs, screenshot placeholder, and notes.
- Portfolio holdings snapshots when positions are open, with weights, risk score, AI score, sector/industry labels, stop, target, holding days, and status.
- 0DTE options foundation output: CALL/PUT intent, same-session expiration, underlying price, strike, max premium budget, and provider-required execution status so the UI can show options planning without fabricating options-chain data.

The endpoint remains:

```bash
curl "http://localhost:8000/api/v1/research/daily-report?capital=10000"
```

## Strategy Lab

The platform includes an additive Strategy Lab at `/strategies` and `GET /api/v1/strategies/lab`.
It preserves existing research APIs while adding executable research workflows for:

- one-click 1, 3, 5, and 10 year backtest horizons;
- multi-strategy comparison and leaderboard ranking;
- walk-forward validation;
- deterministic Monte Carlo scenario analysis;
- SMA parameter optimization;
- feature-importance explanations;
- symbol correlation heatmaps;
- regime-based performance summaries;
- export-ready paper-trading intents that require user confirmation and do not place live orders.

Example:

```bash
curl "http://localhost:8000/api/v1/strategies/lab?horizon_years=5&capital=10000"
```

## Daily Research Strategy Revision

The daily paper-research strategy was revised from a short 20/50 SMA crossover into a more conservative regime-trend model. It now waits for a risk-on regime, deploys most of each symbol sleeve only after trend recovery, exits on trend/regime breaks or trailing-stop failure, and still preserves the platform rule: signal on close, fill on next open. This is intended to reduce short-term whipsaw and improve the poor profit-factor/win-rate profile observed in the earlier analytics screen.
