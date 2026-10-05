"""Workspaces API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user, require_workspace_member
from backend.database import get_db
from backend.middleware.errors import AppError
from backend.models.profile import Profile
from backend.models.workspace import WorkspaceMember
from backend.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from backend.services.workspace import WorkspaceService

router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Create a new workspace and assign the creator as the initial owner."""
    return await WorkspaceService.create_workspace(db, current_user.id, data)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    """List all workspaces that the current user belongs to."""
    return await WorkspaceService.get_user_workspaces(db, current_user.id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Get workspace details. Requires membership."""
    ws = await WorkspaceService.get_workspace_by_id(db, workspace_id, member.user_id)
    if ws is None:
        raise AppError("NOT_FOUND", "Workspace not found", status_code=404)
    return ws


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceMemberResponse]:
    """List all members of a workspace. Requires membership."""
    return await WorkspaceService.get_workspace_members(db, workspace_id)
