"""Unit tests for FastAPI lifespan manager and background worker startup logging."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from backend.config import Settings
from backend.main import lifespan


@pytest.mark.anyio
async def test_lifespan_testing_environment_skips_workers():
    """Verify testing environment does not spawn background worker tasks."""
    app = FastAPI()
    with patch("backend.main.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            ENVIRONMENT="testing",
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        )
        with patch("backend.main.dispose_engine", new_callable=AsyncMock) as mock_dispose:
            async with lifespan(app):
                pass
            mock_dispose.assert_awaited_once()


@pytest.mark.anyio
async def test_lifespan_logs_search_worker_startup_failure(caplog):
    """Verify SearchWorker startup failure is logged with logger.exception without crashing lifespan."""
    app = FastAPI()
    with patch("backend.main.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            ENVIRONMENT="development",
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
            OPENROUTER_API_KEY=None,
        )
        with patch("backend.database.get_session_factory", return_value=MagicMock()):
            with patch(
                "backend.providers.discovery.get_discovery_provider",
                side_effect=RuntimeError("Discovery provider configuration missing"),
            ):
                with patch("backend.main.dispose_engine", new_callable=AsyncMock):
                    with caplog.at_level("ERROR"):
                        async with lifespan(app):
                            pass
                    assert "Failed to initialize or start SearchWorker" in caplog.text
                    assert "Discovery provider configuration missing" in caplog.text


@pytest.mark.anyio
async def test_lifespan_logs_research_worker_startup_failure(caplog):
    """Verify ResearchWorker startup failure is logged with logger.exception without crashing lifespan."""
    app = FastAPI()
    with patch("backend.main.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            ENVIRONMENT="development",
            DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
            OPENROUTER_API_KEY="sk-fake-openrouter-key",
        )
        with patch("backend.database.get_session_factory", return_value=MagicMock()):
            with patch(
                "backend.providers.discovery.get_discovery_provider", return_value=MagicMock()
            ):
                with patch("backend.services.search_worker.SearchWorker.start"):
                    with patch(
                        "backend.services.research_worker.ResearchWorker.start",
                        side_effect=RuntimeError("Research worker connection failure"),
                    ):
                        with patch("backend.main.dispose_engine", new_callable=AsyncMock):
                            with caplog.at_level("ERROR"):
                                async with lifespan(app):
                                    pass
                            assert "Failed to initialize or start ResearchWorker" in caplog.text
                            assert "Research worker connection failure" in caplog.text
