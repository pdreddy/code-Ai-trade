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

```bash
docker compose up --build
```

Services:

- Backend API: <http://localhost:8000>
- Frontend: <http://localhost:3000>
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Quality Checks

```bash
ruff check .
mypy backend tests
pytest
cd frontend && npm run typecheck
cd frontend && npm run build
```
