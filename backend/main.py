"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.api import (
    health_router,
    icps_router,
    profiles_router,
    prospects_router,
    searches_router,
    workspaces_router,
)
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
    settings = get_settings()
    search_worker = None
    research_worker = None
    if settings.ENVIRONMENT != "testing" and settings.DATABASE_URL:
        try:
            from backend.database import get_session_factory
            from backend.providers.ai import get_ai_provider
            from backend.providers.discovery import get_discovery_provider
            from backend.providers.web.fetcher import SecureWebFetcher
            from backend.services.research_worker import ResearchWorker
            from backend.services.search_worker import SearchWorker

            session_factory = get_session_factory()
            discovery_provider = get_discovery_provider(settings)
            search_worker = SearchWorker(
                session_factory=session_factory,
                discovery_provider=discovery_provider,
                poll_interval_seconds=settings.SEARCH_WORKER_POLL_INTERVAL_SECONDS,
                job_timeout_seconds=settings.SEARCH_JOB_TIMEOUT_SECONDS,
            )
            search_worker.start()

            ai_provider = get_ai_provider(settings) if settings.OPENROUTER_API_KEY else None
            fetcher = SecureWebFetcher(settings)
            research_worker = ResearchWorker(
                session_factory=session_factory,
                fetcher=fetcher,
                ai_provider=ai_provider,
                poll_interval_seconds=settings.RESEARCH_WORKER_POLL_INTERVAL_SECONDS,
                job_timeout_seconds=settings.RESEARCH_JOB_TIMEOUT_SECONDS,
            )
            research_worker.start()
        except Exception:
            pass

    yield

    if search_worker:
        await search_worker.stop()
    if research_worker:
        await research_worker.stop()
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
    app.include_router(icps_router)
    app.include_router(searches_router)
    app.include_router(prospects_router)

    return app


app = create_app()
