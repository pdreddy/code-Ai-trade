# Render Deployment Guide

This guide deploys the current platform foundation to Render with a backend web service,
a frontend web service, managed PostgreSQL, and managed Key Value (Redis-compatible)
cache. It is intended for testing the current health endpoint, frontend shell, market-data
provider code paths, and database migrations. Backtester, execution simulator, paper broker, risk engine, analytics, and UI foundation
services are implemented. Live trading remains disabled until live broker adapters, persistent audit
logs, and production risk operations are independently reviewed.

## Architecture

- `ai-quant-backend`: Python web service running FastAPI through Uvicorn.
- `ai-quant-frontend`: Node web service running the Next.js frontend.
- `ai-quant-postgres`: Render-managed PostgreSQL database.
- `ai-quant-redis`: Render Key Value service used as the Redis-compatible cache URL. The Blueprint sets `ipAllowList: []` so only internal Render services can connect.

## Deploy

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, choose **New > Blueprint** and select the repository.
3. Render will detect the root-level `render.yaml` Blueprint.
4. Review the generated backend, frontend, PostgreSQL, and Key Value resources.
5. Apply the Blueprint.
6. Wait for the backend pre-deploy command to run `alembic upgrade head`.
7. Open the backend health endpoint:

   ```bash
   curl https://ai-quant-backend.onrender.com/api/v1/health
   ```

8. Open the frontend:

   ```text
   https://ai-quant-frontend.onrender.com
   ```

## Required Secrets

When Render creates the backend service, enter these secret values in the Blueprint prompt or backend Environment tab:

- `AI_QUANT_MASSIVE_API_KEY`: REST API key for the live options snapshot provider.
- `AI_QUANT_MASSIVE_S3_ACCESS_KEY_ID`: Massive Flat Files access key ID.
- `AI_QUANT_MASSIVE_S3_SECRET_ACCESS_KEY`: Massive Flat Files secret access key.
- `AI_QUANT_TRADIER_API_TOKEN`: optional fallback if you switch `AI_QUANT_OPTIONS_DATA_PROVIDER` back to `tradier`.

Do not commit real keys to `render.yaml`; the Blueprint uses `sync: false` for secrets so Render stores them privately.

## Validate Locally Before Pushing

If the Render CLI is installed and authenticated, validate the Blueprint:

```bash
render blueprints validate render.yaml
```

Also run the repository quality checks:

```bash
ruff check .
mypy backend tests
pytest
cd frontend && npm run typecheck
cd frontend && npm run build
```

## Notes

- The frontend uses `NEXT_PUBLIC_API_BASE_URL=https://ai-quant-backend.onrender.com/api/v1`.
  If you rename the backend service or add a custom domain, update `render.yaml` before syncing.
- Render Key Value requires an `ipAllowList`; this Blueprint blocks external connections with `ipAllowList: []`.
- Render exposes PostgreSQL as a standard `postgresql://` URL. The backend normalizes that to
  SQLAlchemy's `postgresql+psycopg://` dialect at runtime.
- Do not enable real trading from this deployment. The platform currently supports research,
  backtesting foundations, paper-trading foundations, risk checks, and analytics summaries, but
  it does not include live broker adapters or production trading approval workflows.
