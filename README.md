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
