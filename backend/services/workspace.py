"""Workspace domain service."""

import re
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import utc_now
from backend.models.profile import Profile
from backend.models.workspace import Workspace, WorkspaceMember
from backend.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)


def slugify(text: str) -> str:
    """Generate a clean URL-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "workspace"


class WorkspaceService:
    """Domain service managing workspaces and memberships."""

    @staticmethod
    async def create_workspace(
        db: AsyncSession,
        user_id: UUID,
        data: WorkspaceCreate,
    ) -> WorkspaceResponse:
        """Create a workspace and assign the creator as the initial owner."""
        base_slug = data.slug or slugify(data.name)
        slug = base_slug

        # Ensure slug uniqueness
        stmt_check = select(Workspace.id).where(Workspace.slug == slug)
        existing = (await db.execute(stmt_check)).scalar_one_or_none()
        if existing:
            slug = f"{base_slug}-{secrets.token_hex(2)}"

        now = utc_now()
        workspace = Workspace(
            id=uuid4(),
            name=data.name,
            slug=slug,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(workspace)
        await db.flush()

        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace.id,
            user_id=user_id,
            role="owner",
            joined_at=now,
        )
        db.add(member)
        await db.commit()
        await db.refresh(workspace)

        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            created_by=workspace.created_by,
            created_at=workspace.created_at or now,
            updated_at=workspace.updated_at or now,
            role="owner",
        )

    @staticmethod
    async def get_user_workspaces(
        db: AsyncSession,
        user_id: UUID,
    ) -> list[WorkspaceResponse]:
        """List all workspaces that the user belongs to."""
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            WorkspaceResponse(
                id=ws.id,
                name=ws.name,
                slug=ws.slug,
                created_by=ws.created_by,
                created_at=ws.created_at or utc_now(),
                updated_at=ws.updated_at or utc_now(),
                role=role,  # type: ignore[arg-type]
            )
            for ws, role in rows
        ]

    @staticmethod
    async def get_workspace_by_id(
        db: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceResponse | None:
        """Fetch workspace details if user is a member."""
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(Workspace.id == workspace_id, WorkspaceMember.user_id == user_id)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None

        ws, role = row
        return WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            created_by=ws.created_by,
            created_at=ws.created_at or utc_now(),
            updated_at=ws.updated_at or utc_now(),
            role=role,  # type: ignore[arg-type]
        )

    @staticmethod
    async def get_workspace_members(
        db: AsyncSession,
        workspace_id: UUID,
    ) -> list[WorkspaceMemberResponse]:
        """List all members of a workspace."""
        stmt = (
            select(WorkspaceMember, Profile.email, Profile.full_name)
            .join(Profile, WorkspaceMember.user_id == Profile.id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            WorkspaceMemberResponse(
                id=m.id,
                workspace_id=m.workspace_id,
                user_id=m.user_id,
                role=m.role,  # type: ignore[arg-type]
                joined_at=m.joined_at or utc_now(),
                email=email,
                full_name=full_name,
            )
            for m, email, full_name in rows
        ]
