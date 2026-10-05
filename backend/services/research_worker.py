"""Background worker for asynchronous prospect research and qualification."""

import asyncio
from datetime import timedelta
import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.models.base import utc_now
from backend.models.prospect import Prospect
from backend.providers.ai.base import AIProvider
from backend.providers.web.fetcher import SecureWebFetcher
from backend.services.prospect import ProspectService

logger = logging.getLogger(__name__)


class ResearchWorker:
    """Application-lifespan background worker claiming and executing QUEUED prospect research."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        fetcher: SecureWebFetcher,
        ai_provider: AIProvider | None = None,
        poll_interval_seconds: float = 2.0,
        job_timeout_seconds: float = 120.0,
    ) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.ai_provider = ai_provider
        self.poll_interval = poll_interval_seconds
        self.job_timeout = job_timeout_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start the async research worker loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="research-worker")
        logger.info("ResearchWorker started with poll_interval=%.1fs", self.poll_interval)

    async def stop(self) -> None:
        """Stop the async research worker loop gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ResearchWorker stopped")

    async def recover_stale_prospects(self) -> int:
        """Transition prospects stuck in RESEARCHING longer than timeout to FAILED."""
        threshold = utc_now() - timedelta(seconds=self.job_timeout)
        async with self.session_factory() as session:
            stmt = (
                update(Prospect)
                .where(
                    Prospect.status == "RESEARCHING",
                    Prospect.updated_at < threshold,
                )
                .values(
                    status="FAILED",
                    error_code="JOB_STALE_RECOVERED",
                    error_message=f"Research exceeded timeout of {self.job_timeout}s without completion.",
                    updated_at=utc_now(),
                )
            )
            res = await session.execute(stmt)
            await session.commit()
            count = getattr(res, "rowcount", 0) or 0
            if isinstance(count, int) and count > 0:
                logger.warning("Recovered %d stale prospect research jobs to FAILED status", count)
            return int(count)

    async def process_next_batch(self, batch_size: int = 5) -> int:
        """Poll and execute a batch of QUEUED prospects."""
        queued_ids: list[UUID] = []
        async with self.session_factory() as session:
            stmt = (
                select(Prospect.id)
                .where(Prospect.status == "QUEUED")
                .order_by(Prospect.queued_at.asc())
                .limit(batch_size)
            )
            res = await session.execute(stmt)
            queued_ids = list(res.scalars().all())

        if not queued_ids:
            return 0

        for prospect_id in queued_ids:
            if not self._running:
                break
            try:
                async with self.session_factory() as session:
                    await ProspectService.execute_prospect_research(
                        db=session,
                        prospect_id=prospect_id,
                        fetcher=self.fetcher,
                        ai_provider=self.ai_provider,
                    )
            except Exception as exc:
                logger.exception("Unexpected error processing prospect %s: %s", prospect_id, exc)

        return len(queued_ids)

    async def _run_loop(self) -> None:
        """Main poll loop."""
        # Initial stale recovery on startup
        try:
            await self.recover_stale_prospects()
        except Exception as exc:
            logger.warning("Initial research stale recovery failed: %s", exc)

        while self._running:
            try:
                processed = await self.process_next_batch()
                if processed == 0:
                    await asyncio.sleep(self.poll_interval)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in ResearchWorker loop: %s", exc)
                await asyncio.sleep(self.poll_interval)
