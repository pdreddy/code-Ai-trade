# Production Hardening Runbook

## Quality Gates

Every pull request must pass:

- `ruff check .`
- `mypy backend tests`
- `pytest`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

The GitHub Actions workflow in `.github/workflows/quality.yml` runs these checks for backend and frontend changes.

## Observability Baseline

The API health endpoint is the deployment readiness probe. Production deployments should collect:

- HTTP status code and latency by route.
- Error counts by exception type.
- Database connection pool saturation.
- Redis connectivity and command latency.
- Market-data provider request counts, failures, and rate-limit responses.
- Backtest, paper-order, and risk-decision event counts once persistence adapters are added.

## Security Baseline

- Disable FastAPI docs in production.
- Restrict CORS origins to deployed frontend origins.
- Keep secrets in platform-managed environment variables.
- Never expose live brokerage controls until broker adapters, risk controls, audit logs, and kill-switch operations are independently reviewed.

## Backup And Restore

- PostgreSQL must use managed automated backups in production.
- Before destructive migrations, run a manual snapshot.
- Restore drills should validate instruments, bars, corporate actions, ingestion batches, decisions, orders, trades, and risk decisions once those persistence adapters exist.

## Deployment Runbook

1. Merge only after the quality workflow passes.
2. Render runs `alembic upgrade head` before backend startup.
3. Confirm `/api/v1/health` returns `status=ok`.
4. Confirm the frontend route build includes Dashboard, Watchlists, Signals, Stock Details, Backtests, Paper Trades, Portfolio, and Analytics.
5. Keep real trading disabled until live broker adapters and production risk sign-off exist.
