"""ICP domain service.

Manages ICP persistence, state transitions, validation, and AI compilation.
Enforces workspace isolation and role-based permissions.
"""

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.middleware.errors import AppError
from backend.models.base import utc_now
from backend.models.icp import ICP
from backend.providers.ai.base import AIProvider
from backend.schemas.icp import ICPCreate, ICPStatus, ICPUpdate

logger = logging.getLogger(__name__)

# Valid state transitions: current_status -> set of allowed next_statuses
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"COMPILED", "ARCHIVED"},
    "COMPILED": {"APPROVED", "DRAFT", "ARCHIVED"},
    "APPROVED": {"ARCHIVED"},
    "ARCHIVED": set(),  # Terminal state
}


class ICPService:
    """Domain service for ICP lifecycle and compilation."""

    @staticmethod
    async def create_icp(
        db: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
        data: ICPCreate,
    ) -> ICP:
        """Create a new ICP in DRAFT status."""
        name = data.name.strip()
        raw_prompt = data.raw_prompt.strip()

        if not name:
            raise AppError("VALIDATION_ERROR", "ICP name cannot be empty.", status_code=422)
        if not raw_prompt:
            raise AppError("VALIDATION_ERROR", "ICP prompt cannot be empty.", status_code=422)

        now = utc_now()
        icp = ICP(
            id=uuid4(),
            workspace_id=workspace_id,
            created_by=user_id,
            name=name,
            raw_prompt=raw_prompt,
            status="DRAFT",
            version=1,
            compiled_criteria=None,
            compilation_error=None,
            created_at=now,
            updated_at=now,
        )
        db.add(icp)
        await db.commit()
        await db.refresh(icp)
        return icp

    @staticmethod
    async def get_icp_by_id(
        db: AsyncSession,
        workspace_id: UUID,
        icp_id: UUID,
    ) -> ICP:
        """Get an ICP by ID scoped to a specific workspace.

        Returns 404 if not found or belongs to another workspace.
        """
        stmt = select(ICP).where(ICP.id == icp_id, ICP.workspace_id == workspace_id)
        result = await db.execute(stmt)
        icp = result.scalar_one_or_none()
        if icp is None:
            raise AppError("NOT_FOUND", "ICP not found", status_code=404)
        return icp

    @staticmethod
    async def list_icps(
        db: AsyncSession,
        workspace_id: UUID,
        status: ICPStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ICP]:
        """List ICPs in a workspace, optionally filtered by status."""
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        stmt = (
            select(ICP)
            .where(ICP.workspace_id == workspace_id)
            .order_by(ICP.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(ICP.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_icp(
        db: AsyncSession,
        workspace_id: UUID,
        icp_id: UUID,
        data: ICPUpdate,
        user_role: str,
    ) -> ICP:
        """Update ICP details and/or transition its lifecycle status."""
        icp = await ICPService.get_icp_by_id(db, workspace_id, icp_id)

        # ARCHIVED is terminal
        if icp.status == "ARCHIVED":
            raise AppError(
                "INVALID_STATE_TRANSITION",
                "Cannot modify an archived ICP.",
                status_code=409,
            )

        # 1. Check archive permission
        if data.status == "ARCHIVED" and user_role != "owner":
            raise AppError(
                "FORBIDDEN_OPERATION",
                "Only workspace owners can archive an ICP.",
                status_code=403,
            )

        # 2. Validate status transition if status is changing
        if data.status is not None and data.status != icp.status:
            allowed_next = ALLOWED_TRANSITIONS.get(icp.status, set())
            if data.status not in allowed_next:
                raise AppError(
                    "INVALID_STATE_TRANSITION",
                    f"Invalid status transition from {icp.status} to {data.status}.",
                    status_code=409,
                )

            # Validating prerequisite for APPROVED status
            if data.status == "APPROVED" and not icp.compiled_criteria:
                raise AppError(
                    "INVALID_STATE_TRANSITION",
                    "Cannot approve an ICP without compiled criteria.",
                    status_code=409,
                )

            icp.status = data.status

        # 3. Handle prompt update and possible reversion to DRAFT
        if data.raw_prompt is not None:
            new_prompt = data.raw_prompt.strip()
            if not new_prompt:
                raise AppError("VALIDATION_ERROR", "ICP prompt cannot be empty.", status_code=422)
            if new_prompt != icp.raw_prompt:
                icp.raw_prompt = new_prompt
                # Editing prompt reverts COMPILED back to DRAFT
                if icp.status == "COMPILED":
                    icp.status = "DRAFT"
                icp.version += 1

        # 4. Handle name update
        if data.name is not None:
            new_name = data.name.strip()
            if not new_name:
                raise AppError("VALIDATION_ERROR", "ICP name cannot be empty.", status_code=422)
            icp.name = new_name

        icp.updated_at = utc_now()
        await db.commit()
        await db.refresh(icp)
        return icp

    @staticmethod
    async def compile_icp(
        db: AsyncSession,
        workspace_id: UUID,
        icp_id: UUID,
        ai_provider: AIProvider,
    ) -> ICP:
        """Compile an ICP's raw prompt using the configured AIProvider."""
        icp = await ICPService.get_icp_by_id(db, workspace_id, icp_id)

        if icp.status == "ARCHIVED":
            raise AppError(
                "INVALID_STATE_TRANSITION",
                "Cannot compile an archived ICP.",
                status_code=409,
            )

        if icp.status == "APPROVED":
            raise AppError(
                "INVALID_STATE_TRANSITION",
                "Cannot compile an approved ICP. Update prompt to revert to draft first.",
                status_code=409,
            )

        try:
            criteria = await ai_provider.compile_icp(icp.raw_prompt)
            icp.compiled_criteria = criteria.model_dump(mode="json")
            icp.compilation_error = None
            icp.status = "COMPILED"
            icp.version += 1
            icp.updated_at = utc_now()
            await db.commit()
            await db.refresh(icp)
            return icp
        except AppError as exc:
            # Record compilation error in the ICP row for audit/debugging
            icp.compilation_error = exc.message
            icp.updated_at = utc_now()
            await db.commit()
            await db.refresh(icp)
            raise
