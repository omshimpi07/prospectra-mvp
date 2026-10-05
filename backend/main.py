"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.api import health_router, profiles_router, workspaces_router
from backend.config import get_settings
from backend.database import dispose_engine
from backend.middleware.errors import register_error_handlers


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach correlation request ID to request state and response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Prospectra API",
        version="0.1.0",
        description="Prospect Intelligence Platform API",
        lifespan=lifespan,
    )

    # 1. Error handlers
    register_error_handlers(app)

    # 2. Request ID correlation
    app.add_middleware(RequestIDMiddleware)

    # 3. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Routers
    app.include_router(health_router)
    app.include_router(profiles_router)
    app.include_router(workspaces_router)

    return app


app = create_app()
