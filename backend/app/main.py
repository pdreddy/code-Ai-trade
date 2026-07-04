"""FastAPI application factory for the AI Quant Platform."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.capabilities import router as capabilities_router
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.market_data import router as market_data_router
from backend.app.api.v1.research import router as research_router
from backend.app.core.config import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hook reserved for managed resources."""

    app.state.settings = get_settings()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        docs_url="/docs" if resolved_settings.environment != "production" else None,
        redoc_url="/redoc" if resolved_settings.environment != "production" else None,
        openapi_url="/openapi.json" if resolved_settings.environment != "production" else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(capabilities_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(analytics_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(market_data_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(research_router, prefix=resolved_settings.api_v1_prefix)
    return app


app = create_app()
