import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import DateTime
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend import database
from backend.config import get_settings
from backend.models import Base, TimestampMixin
from backend.models.base import utc_now

TEST_DATABASE_URL = "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"


# Captured at import time: tests below monkeypatch the module attributes with
# plain lambdas, which have no cache_clear().
REAL_GET_ENGINE = database.get_engine
REAL_GET_SESSION_FACTORY = database.get_session_factory


def clear_caches() -> None:
    get_settings.cache_clear()
    REAL_GET_ENGINE.cache_clear()
    REAL_GET_SESSION_FACTORY.cache_clear()


@pytest.fixture(autouse=True)
def database_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    clear_caches()
    yield
    clear_caches()


# --- fakes for the engine / session boundary (no network, no real database) ---


class FakeSession:
    def __init__(self):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        self.closed = True
        return False


class FakeEngine:
    """Stands in for AsyncEngine: ``connect()`` is an async context manager."""

    def __init__(self, error: BaseException | None = None):
        self.error = error
        self.connection = AsyncMock()

    def connect(self):
        return self

    async def __aenter__(self):
        if self.error is not None:
            raise self.error
        return self.connection

    async def __aexit__(self, *exc_info):
        return False


# --- engine and session factory ---


def test_engine_is_async_psycopg_with_conservative_pool():
    engine = database.get_engine()

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.dialect.is_async
    assert engine.sync_engine.pool.size() == 5
    assert database.get_engine() is engine


def test_session_factory_builds_async_sessions():
    factory = database.get_session_factory()

    assert factory.class_ is AsyncSession
    assert factory.kw["expire_on_commit"] is False
    assert database.get_session_factory() is factory


# --- get_db lifecycle ---


def test_get_db_yields_session_and_closes_it(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(database, "get_session_factory", lambda: lambda: fake_session)

    async def scenario():
        generator = database.get_db()
        session = await generator.__anext__()
        assert session is fake_session
        assert fake_session.closed is False
        with pytest.raises(StopAsyncIteration):
            await generator.__anext__()
        assert fake_session.closed is True

    asyncio.run(scenario())


def test_get_db_closes_session_when_the_request_fails(monkeypatch):
    fake_session = FakeSession()
    monkeypatch.setattr(database, "get_session_factory", lambda: lambda: fake_session)

    async def scenario():
        generator = database.get_db()
        await generator.__anext__()
        with pytest.raises(RuntimeError):
            await generator.athrow(RuntimeError("request failed"))
        assert fake_session.closed is True

    asyncio.run(scenario())


def test_get_db_yields_a_real_async_session_without_connecting():
    async def scenario():
        generator = database.get_db()
        session = await generator.__anext__()
        assert isinstance(session, AsyncSession)
        await generator.aclose()

    asyncio.run(scenario())


# --- check_database_connection ---


def test_connection_check_success_runs_select_1(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setattr(database, "get_engine", lambda: engine)

    assert asyncio.run(database.check_database_connection()) is True

    engine.connection.execute.assert_awaited_once()
    assert str(engine.connection.execute.call_args.args[0]) == "SELECT 1"


@pytest.mark.parametrize(
    "error",
    [
        OperationalError(
            "SELECT 1", None, Exception("host=db.internal user=admin password=hunter2")
        ),
        OSError("network unreachable"),
    ],
)
def test_connection_check_failure_returns_false_without_leaking_details(
    monkeypatch, caplog, error
):
    monkeypatch.setattr(database, "get_engine", lambda: FakeEngine(error=error))

    with caplog.at_level(logging.WARNING, logger="backend.database"):
        assert asyncio.run(database.check_database_connection()) is False

    assert type(error).__name__ in caplog.text
    for sensitive in ("hunter2", "db.internal", "admin", TEST_DATABASE_URL):
        assert sensitive not in caplog.text


def test_connection_check_does_not_swallow_unexpected_errors(monkeypatch):
    monkeypatch.setattr(database, "get_engine", lambda: FakeEngine(error=ValueError("bug")))

    with pytest.raises(ValueError):
        asyncio.run(database.check_database_connection())


# --- declarative base and timestamp mixin ---


class _LocalBase(DeclarativeBase):
    """Separate base so this test never registers a table on the real Base."""


class _StampedExample(_LocalBase, TimestampMixin):
    __tablename__ = "stamped_example"

    id: Mapped[int] = mapped_column(primary_key=True)


def test_base_declares_models():
    assert issubclass(Base, DeclarativeBase)
    assert {"profiles", "workspaces", "workspace_members"}.issubset(Base.metadata.tables.keys())


def test_utc_now_is_timezone_aware_utc():
    value = utc_now()

    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


@pytest.mark.parametrize("column_name", ["created_at", "updated_at"])
def test_timestamp_columns_are_timezone_aware_and_required(column_name):
    column = _StampedExample.__table__.c[column_name]

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.default is not None
    assert column.server_default is not None


def test_updated_at_refreshes_on_update():
    assert _StampedExample.__table__.c.updated_at.onupdate is not None
    assert _StampedExample.__table__.c.created_at.onupdate is None
