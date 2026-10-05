"""Prospect intelligence, qualification, and scoring endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_workspace_member
from backend.database import get_db
from backend.models.workspace import WorkspaceMember
from backend.schemas.prospect import (
    EvidenceResponse,
    ProspectResponse,
    QualificationStatus,
    QualifyCandidatesRequest,
    QualifyCandidatesResponse,
    RescoreResponse,
)
from backend.services.prospect import ProspectService

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/prospects",
    tags=["Prospects"],
)


@router.post(
    "/qualify-candidates",
    response_model=QualifyCandidatesResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue discovered candidates for qualification research",
)
async def qualify_candidates(
    workspace_id: UUID,
    payload: QualifyCandidatesRequest,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> QualifyCandidatesResponse:
    """Promote search results into the workspace qualification pipeline and queue research."""
    return await ProspectService.qualify_candidates(
        db=db,
        workspace_id=workspace_id,
        search_result_ids=payload.search_result_ids,
    )


@router.get(
    "",
    response_model=list[ProspectResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspace prospects with score-first ranking and optional filters",
)
async def list_prospects(
    workspace_id: UUID,
    qualification_status: QualificationStatus | None = Query(
        default=None, description="Filter by qualification status"
    ),
    min_score: float | None = Query(
        default=None, ge=0.0, le=1.0, description="Minimum priority score filter"
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Max prospects to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[ProspectResponse]:
    """Retrieve paginated prospects ranked deterministically by priority_score DESC."""
    prospects = await ProspectService.list_prospects(
        db=db,
        workspace_id=workspace_id,
        qualification_status=qualification_status,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    return [ProspectResponse.model_validate(p) for p in prospects]


# Static route /rescore is explicitly placed BEFORE dynamic /{prospect_id} to avoid route collision
@router.post(
    "/rescore",
    response_model=RescoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Recompute opportunity scores for all prospects in the workspace",
)
async def rescore_prospects(
    workspace_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> RescoreResponse:
    """Re-evaluate opportunity scores and factor breakdowns across all workspace prospects."""
    return await ProspectService.rescore_workspace_prospects(
        db=db,
        workspace_id=workspace_id,
    )


@router.get(
    "/{prospect_id}",
    response_model=ProspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single prospect details, score breakdown, and qualification status",
)
async def get_prospect(
    workspace_id: UUID,
    prospect_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> ProspectResponse:
    """Retrieve detailed qualification facts, score breakdown, and rationale for a single prospect."""
    prospect = await ProspectService.get_prospect_by_id(
        db=db,
        workspace_id=workspace_id,
        prospect_id=prospect_id,
    )
    return ProspectResponse.model_validate(prospect)


@router.get(
    "/{prospect_id}/evidence",
    response_model=list[EvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="List auditable evidence items supporting prospect qualification",
)
async def get_prospect_evidence(
    workspace_id: UUID,
    prospect_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceResponse]:
    """Retrieve all atomic evidence items collected during prospect research."""
    evidence_items = await ProspectService.list_evidence(
        db=db,
        workspace_id=workspace_id,
        prospect_id=prospect_id,
    )
    return [EvidenceResponse.model_validate(e) for e in evidence_items]


@router.post(
    "/{prospect_id}/requalify",
    response_model=ProspectResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-enqueue an existing prospect for qualification",
)
async def requalify_prospect(
    workspace_id: UUID,
    prospect_id: UUID,
    _member: WorkspaceMember = Depends(require_workspace_member()),
    db: AsyncSession = Depends(get_db),
) -> ProspectResponse:
    """Reset prospect state to QUEUED and trigger fresh research & qualification."""
    prospect = await ProspectService.requalify_prospect(
        db=db,
        workspace_id=workspace_id,
        prospect_id=prospect_id,
    )
    return ProspectResponse.model_validate(prospect)
