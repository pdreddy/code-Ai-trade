"""Health and readiness endpoints."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from backend.app.core.config import Settings, get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Public health contract used by load balancers and smoke tests."""

    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    environment: str
    demo_mode: bool
    market_data_provider: str
    timestamp_utc: datetime


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Return process-level health without touching external dependencies."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
        demo_mode=settings.demo_mode,
        market_data_provider=settings.market_data_provider,
        timestamp_utc=datetime.now(UTC),
    )
