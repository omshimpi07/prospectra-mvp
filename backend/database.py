"""Async database access (SQLAlchemy 2.x + psycopg 3).

The engine and session factory are created lazily on first use, so importing this
module has no side effects and never requires configuration to be present.
"""

import logging
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the shared async engine (one conservative pool for the whole app)."""
    return create_async_engine(
        get_settings().DATABASE_URL.get_secret_value(),
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args={
            # Fail fast instead of hanging when the database is unreachable.
            "connect_timeout": 10,
            # Supabase's pooler in transaction mode does not support the
            # server-side prepared statements psycopg 3 creates by default.
            "prepare_threshold": None,
        },
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding one AsyncSession per request.

    The session is always closed afterwards. Transaction control (commit) is left
    to the caller; closing without a commit rolls back any pending work.
    """
    async with get_session_factory()() as session:
        yield session


async def check_database_connection() -> bool:
    """Run ``SELECT 1``; return False on expected connection failures.

    Only the exception class is logged, because driver messages can include host
    and user details.
    """
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        logger.warning("Database connection check failed: %s", type(exc).__name__)
        return False
    return True


async def dispose_engine() -> None:
    """Close pooled connections; intended for application shutdown."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
