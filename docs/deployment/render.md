# Render Deployment Guide

This guide deploys the current platform foundation to Render with a backend web service,
a frontend web service, managed PostgreSQL, and managed Key Value (Redis-compatible)
cache. It is intended for testing the current health endpoint, frontend shell, market-data
provider code paths, and database migrations. Paper trading and live success-rate tracking
are not ready until the backtester, execution simulator, paper broker, risk engine, and UI
milestones are implemented.

## Architecture

- `koc3-quant-backend`: Python web service running FastAPI through Uvicorn.
- `koc3-quant-frontend`: Node web service running the Next.js frontend.
- `koc3-quant-postgres`: Render-managed PostgreSQL database.
- `koc3-quant-redis`: Render Key Value service used as the Redis-compatible cache URL. The Blueprint sets `ipAllowList: []` so only internal Render services can connect.

## Deploy

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, choose **New > Blueprint** and select the repository.
3. Render will detect the root-level `render.yaml` Blueprint.
4. Review the generated backend, frontend, PostgreSQL, and Key Value resources.
5. Apply the Blueprint.
6. Wait for the backend pre-deploy command to run `alembic upgrade head`.
7. Open the backend health endpoint:

   ```bash
   curl https://koc3-quant-backend.onrender.com/api/v1/health
   ```

8. Open the frontend:

   ```text
   https://koc3-quant-frontend.onrender.com
   ```

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

- The frontend uses `NEXT_PUBLIC_API_BASE_URL=https://koc3-quant-backend.onrender.com/api/v1`.
  If you rename the backend service or add a custom domain, update `render.yaml` before syncing.
- Render Key Value requires an `ipAllowList`; this Blueprint blocks external connections with `ipAllowList: []`.
- Render exposes PostgreSQL as a standard `postgresql://` URL. The backend normalizes that to
  SQLAlchemy's `postgresql+psycopg://` dialect at runtime.
- Do not enable real trading from this deployment. The current milestone set does not yet include
  the event-driven backtester, paper broker, risk engine, or live broker adapters.
