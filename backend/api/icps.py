"""ICPs API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_workspace_member
from backend.database import get_db
from backend.models.workspace import WorkspaceMember
from backend.providers.ai.base import AIProvider
from backend.providers.ai.factory import get_ai_provider
from backend.schemas.icp import ICPCreate, ICPResponse, ICPStatus, ICPUpdate
from backend.services.icp import ICPService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/icps", tags=["ICPs"])


@router.post("", response_model=ICPResponse, status_code=status.HTTP_201_CREATED)
async def create_icp(
    workspace_id: UUID,
    data: ICPCreate,
    member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> ICPResponse:
    """Create a new ICP draft in the target workspace."""
    icp = await ICPService.create_icp(
        db=db,
        workspace_id=workspace_id,
        user_id=member.user_id,
        data=data,
    )
    return ICPResponse.model_validate(icp)


@router.get("", response_model=list[ICPResponse])
async def list_icps(
    workspace_id: UUID,
    status_filter: ICPStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[ICPResponse]:
    """List all ICPs in a workspace, optionally filtered by status."""
    icps = await ICPService.list_icps(
        db=db,
        workspace_id=workspace_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [ICPResponse.model_validate(item) for item in icps]


@router.get("/{icp_id}", response_model=ICPResponse)
async def get_icp(
    workspace_id: UUID,
    icp_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> ICPResponse:
    """Get single ICP details scoped to the workspace."""
    icp = await ICPService.get_icp_by_id(db=db, workspace_id=workspace_id, icp_id=icp_id)
    return ICPResponse.model_validate(icp)


@router.patch("/{icp_id}", response_model=ICPResponse)
async def update_icp(
    workspace_id: UUID,
    icp_id: UUID,
    data: ICPUpdate,
    member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> ICPResponse:
    """Update ICP fields or transition lifecycle status.

    Archiving (status='ARCHIVED') requires workspace owner role.
    """
    icp = await ICPService.update_icp(
        db=db,
        workspace_id=workspace_id,
        icp_id=icp_id,
        data=data,
        user_role=member.role,
    )
    return ICPResponse.model_validate(icp)


@router.post("/{icp_id}/compile", response_model=ICPResponse)
async def compile_icp(
    workspace_id: UUID,
    icp_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
    ai_provider: AIProvider = Depends(get_ai_provider),
) -> ICPResponse:
    """Compile raw natural language prompt into structured ICP criteria using AI."""
    icp = await ICPService.compile_icp(
        db=db,
        workspace_id=workspace_id,
        icp_id=icp_id,
        ai_provider=ai_provider,
    )
    return ICPResponse.model_validate(icp)
