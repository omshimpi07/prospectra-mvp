"""Health check endpoint."""

from fastapi import APIRouter

from backend.database import check_database_connection
from backend.models.base import utc_now
from backend.schemas.common import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return backend health and database connectivity status."""
    db_connected = await check_database_connection()
    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        database="connected" if db_connected else "disconnected",
        timestamp=utc_now(),
        version="0.1.0",
    )
