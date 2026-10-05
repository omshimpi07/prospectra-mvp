"""Search domain service.

Manages Search lifecycle, conversion from APPROVED ICP to SearchSpecification,
job queueing, and candidate persistence.
"""

import logging
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.errors import AppError
from backend.models.base import utc_now
from backend.models.geography import calculate_bounding_box, get_city_centroid
from backend.models.icp import ICP
from backend.models.search import Search, SearchResult
from backend.providers.discovery.base import DiscoveryProvider
from backend.schemas.search import (
    GeoBoundingBox,
    SearchCreate,
    SearchResultResponse,
    SearchSpecification,
    SearchStatus,
)

logger = logging.getLogger(__name__)


class SearchService:
    """Domain service for Search management and execution."""

    @staticmethod
    async def create_search(
        db: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        data: SearchCreate,
    ) -> Search:
        """Create a new Search specification from an APPROVED ICP."""
        # 1. Fetch and validate ICP
        stmt_icp = select(ICP).where(ICP.id == data.icp_id, ICP.workspace_id == workspace_id)
        result_icp = await db.execute(stmt_icp)
        icp = result_icp.scalar_one_or_none()

        if icp is None:
            raise AppError("NOT_FOUND", "Target ICP not found in workspace.", status_code=404)

        if icp.status != "APPROVED":
            raise AppError(
                "INVALID_ICP_STATUS",
                f"Only APPROVED ICPs can be used to create a search (current status: '{icp.status}').",
                status_code=409,
            )

        if not icp.compiled_criteria or not isinstance(icp.compiled_criteria, dict):
            raise AppError(
                "INVALID_ICP_STATUS",
                "Approved ICP is missing compiled criteria.",
                status_code=409,
            )

        # 2. Check Idempotency Key
        if data.idempotency_key:
            stmt_idemp = select(Search).where(
                Search.workspace_id == workspace_id,
                Search.idempotency_key == data.idempotency_key,
            )
            res_idemp = await db.execute(stmt_idemp)
            existing = res_idemp.scalar_one_or_none()
            if existing:
                logger.info(
                    "Returning existing search for idempotency_key=%s", data.idempotency_key
                )
                return existing

        # 3. Derive SearchSpecification from compiled criteria
        criteria = icp.compiled_criteria
        location_data = criteria.get("location", {})
        city = location_data.get("city")
        if not city:
            raise AppError(
                "INVALID_ICP_STATUS", "ICP location does not specify a city.", status_code=422
            )

        target_categories = criteria.get("target_categories", [])
        if not target_categories:
            raise AppError(
                "INVALID_ICP_STATUS",
                "ICP criteria does not contain target categories.",
                status_code=422,
            )

        # Resolve geographic centroid and bounding box
        center_lat, center_lon = get_city_centroid(city)
        radius = data.radius_km
        min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(center_lat, center_lon, radius)

        spec = SearchSpecification(
            target_categories=target_categories,
            city=city,
            state_province=location_data.get("state_province"),
            country=location_data.get("country"),
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius,
            bounding_box=GeoBoundingBox(
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
            ),
            limit=data.limit,
        )

        now = utc_now()
        search = Search(
            id=uuid4(),
            workspace_id=workspace_id,
            icp_id=data.icp_id,
            created_by=user_id,
            status="CREATED",
            idempotency_key=data.idempotency_key,
            specification=spec.model_dump(mode="json"),
            total_candidates=0,
            new_candidates=0,
            error_code=None,
            error_message=None,
            queued_at=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(search)
        await db.commit()
        await db.refresh(search)
        return search

    @staticmethod
    async def get_search_by_id(
        db: AsyncSession,
        workspace_id: UUID,
        search_id: UUID,
    ) -> Search:
        """Get single search scoped to workspace."""
        stmt = select(Search).where(Search.id == search_id, Search.workspace_id == workspace_id)
        result = await db.execute(stmt)
        search = result.scalar_one_or_none()
        if search is None:
            raise AppError("NOT_FOUND", "Search not found", status_code=404)
        return search

    @staticmethod
    async def list_searches(
        db: AsyncSession,
        workspace_id: UUID,
        status: SearchStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Search]:
        """List searches in workspace with pagination and optional status filter."""
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        stmt = (
            select(Search)
            .where(Search.workspace_id == workspace_id)
            .order_by(Search.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Search.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def queue_search(
        db: AsyncSession,
        workspace_id: UUID,
        search_id: UUID,
    ) -> Search:
        """Transition search from CREATED/FAILED to QUEUED for worker execution."""
        search = await SearchService.get_search_by_id(db, workspace_id, search_id)

        if search.status in ("QUEUED", "RUNNING"):
            raise AppError(
                "INVALID_STATE_TRANSITION",
                f"Search is already in progress ({search.status}).",
                status_code=409,
            )

        if search.status == "COMPLETED":
            raise AppError(
                "INVALID_STATE_TRANSITION",
                "Search has already completed successfully.",
                status_code=409,
            )

        now = utc_now()
        search.status = "QUEUED"
        search.queued_at = now
        search.error_code = None
        search.error_message = None
        search.updated_at = now

        await db.commit()
        await db.refresh(search)
        return search

    @staticmethod
    async def list_search_results(
        db: AsyncSession,
        workspace_id: UUID,
        search_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResultResponse]:
        """List discovered candidates for a search."""
        # Ensure search exists and belongs to workspace
        await SearchService.get_search_by_id(db, workspace_id, search_id)

        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        stmt = (
            select(SearchResult)
            .where(
                SearchResult.search_id == search_id,
                SearchResult.workspace_id == workspace_id,
            )
            .order_by(SearchResult.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        return [SearchResultResponse.model_validate(r) for r in items]

    @staticmethod
    async def execute_search(
        db: AsyncSession,
        search_id: UUID,
        discovery_provider: DiscoveryProvider,
    ) -> Search:
        """Atomically claim a QUEUED search, execute discovery, and persist results."""
        now = utc_now()

        # Atomic claim: transition QUEUED -> RUNNING
        stmt_claim = (
            update(Search)
            .where(Search.id == search_id, Search.status == "QUEUED")
            .values(status="RUNNING", started_at=now, updated_at=now)
            .returning(Search)
        )
        res_claim = await db.execute(stmt_claim)
        search = res_claim.scalar_one_or_none()
        await db.commit()

        if not search:
            # Already claimed or no longer in QUEUED state
            stmt_curr = select(Search).where(Search.id == search_id)
            res_curr = await db.execute(stmt_curr)
            return res_curr.scalar_one()

        try:
            spec = SearchSpecification.model_validate(search.specification)
            candidates = await discovery_provider.discover_businesses(spec)

            # Persist candidates
            results_to_insert: list[SearchResult] = []
            for cand in candidates:
                results_to_insert.append(
                    SearchResult(
                        id=uuid4(),
                        search_id=search.id,
                        workspace_id=search.workspace_id,
                        external_id=cand.external_id,
                        provider="overture",
                        name=cand.name,
                        canonical_category=cand.canonical_category,
                        raw_category=cand.raw_category,
                        latitude=cand.latitude,
                        longitude=cand.longitude,
                        address=cand.address,
                        city=cand.city,
                        postal_code=cand.postal_code,
                        phone=cand.phone,
                        website=cand.website,
                        confidence=cand.confidence,
                        raw_metadata=cand.raw_metadata,
                        created_at=now,
                    )
                )

            if results_to_insert:
                db.add_all(results_to_insert)

            fin_now = utc_now()
            search.status = "COMPLETED"
            search.finished_at = fin_now
            search.total_candidates = len(candidates)
            search.new_candidates = len(candidates)
            search.updated_at = fin_now
            await db.commit()
            await db.refresh(search)
            return search

        except Exception as exc:
            logger.exception("Error executing search %s: %s", search_id, exc)
            fin_now = utc_now()
            search.status = "FAILED"
            search.finished_at = fin_now
            search.error_code = getattr(exc, "code", "EXECUTION_ERROR")
            search.error_message = str(exc)
            search.updated_at = fin_now
            await db.commit()
            await db.refresh(search)
            return search
