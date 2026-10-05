"""Searches API router."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_workspace_member
from backend.database import get_db
from backend.models.workspace import WorkspaceMember
from backend.schemas.search import (
    SearchCreate,
    SearchResponse,
    SearchResultResponse,
    SearchStatus,
)
from backend.services.search import SearchService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/searches", tags=["Searches"])


@router.post("", response_model=SearchResponse, status_code=status.HTTP_201_CREATED)
async def create_search(
    workspace_id: UUID,
    data: SearchCreate,
    member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Create a new Search specification from an APPROVED ICP."""
    search = await SearchService.create_search(
        db=db,
        workspace_id=workspace_id,
        user_id=member.user_id,
        data=data,
    )
    return SearchResponse.model_validate(search)


@router.get("", response_model=list[SearchResponse])
async def list_searches(
    workspace_id: UUID,
    status_filter: SearchStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResponse]:
    """List searches in workspace, optionally filtered by status."""
    searches = await SearchService.list_searches(
        db=db,
        workspace_id=workspace_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [SearchResponse.model_validate(s) for s in searches]


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search(
    workspace_id: UUID,
    search_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Get single search details scoped to workspace."""
    search = await SearchService.get_search_by_id(
        db=db, workspace_id=workspace_id, search_id=search_id
    )
    return SearchResponse.model_validate(search)


@router.post("/{search_id}/run", response_model=SearchResponse)
async def run_search(
    workspace_id: UUID,
    search_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Queue search for worker execution."""
    search = await SearchService.queue_search(
        db=db,
        workspace_id=workspace_id,
        search_id=search_id,
    )
    return SearchResponse.model_validate(search)


@router.get("/{search_id}/results", response_model=list[SearchResultResponse])
async def list_search_results(
    workspace_id: UUID,
    search_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResultResponse]:
    """List discovered business candidates for a search."""
    return await SearchService.list_search_results(
        db=db,
        workspace_id=workspace_id,
        search_id=search_id,
        limit=limit,
        offset=offset,
    )
