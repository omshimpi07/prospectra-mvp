"""API routers package."""

from backend.api.health import router as health_router
from backend.api.icps import router as icps_router
from backend.api.profiles import router as profiles_router
from backend.api.workspaces import router as workspaces_router

__all__ = ["health_router", "icps_router", "profiles_router", "workspaces_router"]
