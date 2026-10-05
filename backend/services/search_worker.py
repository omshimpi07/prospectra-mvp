"""Single-process asynchronous search worker for MVP job execution.

Runs within application lifespan to poll QUEUED searches, claim them atomically,
execute discovery, and recover stale jobs without requiring Redis/Celery.
"""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.base import utc_now
from backend.models.search import Search
from backend.providers.discovery.base import DiscoveryProvider
from backend.services.search import SearchService

logger = logging.getLogger(__name__)


class SearchWorker:
    """In-process async worker loop managing Search job claims and execution."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        discovery_provider: DiscoveryProvider,
        poll_interval_seconds: float = 2.0,
        job_timeout_seconds: float = 300.0,
    ) -> None:
        self.session_factory = session_factory
        self.discovery_provider = discovery_provider
        self.poll_interval = poll_interval_seconds
        self.job_timeout = job_timeout_seconds
        self._is_running = False
        self._task: asyncio.Task[Any] | None = None

    async def recover_stale_searches(self) -> int:
        """Recover searches stuck in RUNNING or QUEUED past timeout on startup."""
        threshold = utc_now() - timedelta(seconds=self.job_timeout)
        async with self.session_factory() as session:
            stmt = (
                update(Search)
                .where(
                    Search.status.in_(["RUNNING", "QUEUED"]),
                    Search.updated_at < threshold,
                )
                .values(
                    status="FAILED",
                    error_code="JOB_STALE_RECOVERED",
                    error_message=f"Search exceeded timeout of {self.job_timeout}s without completion.",
                    finished_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
            res = await session.execute(stmt)
            await session.commit()
            count = getattr(res, "rowcount", 0) or 0
            if isinstance(count, int) and count > 0:
                logger.warning("Recovered %d stale search jobs to FAILED status", count)
            return int(count)

    async def process_next_batch(self, batch_size: int = 5) -> int:
        """Poll and execute a batch of QUEUED searches."""
        queued_ids: list[Any] = []
        async with self.session_factory() as session:
            stmt = (
                select(Search.id)
                .where(Search.status == "QUEUED")
                .order_by(Search.queued_at.asc())
                .limit(batch_size)
            )
            res = await session.execute(stmt)
            queued_ids = list(res.scalars().all())

        if not queued_ids:
            return 0

        for search_id in queued_ids:
            async with self.session_factory() as session:
                await SearchService.execute_search(session, search_id, self.discovery_provider)

        return len(queued_ids)

    async def _worker_loop(self) -> None:
        """Continuous polling loop."""
        logger.info("SearchWorker loop started (poll_interval=%ss)", self.poll_interval)
        try:
            # 1. Initial recovery on startup
            await self.recover_stale_searches()

            while self._is_running:
                try:
                    processed = await self.process_next_batch()
                    if processed == 0:
                        await asyncio.sleep(self.poll_interval)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.error("Error in SearchWorker loop: %s", exc, exc_info=True)
                    await asyncio.sleep(self.poll_interval)
        finally:
            logger.info("SearchWorker loop terminated.")

    def start(self) -> None:
        """Start background loop task."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stop background loop task gracefully."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
