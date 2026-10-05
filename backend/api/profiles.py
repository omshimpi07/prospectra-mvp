"""Profile API router."""

from fastapi import APIRouter, Depends

from backend.auth.dependencies import get_current_user
from backend.models.profile import Profile
from backend.schemas.profile import ProfileResponse

router = APIRouter(prefix="/api/v1/profiles", tags=["Profiles"])


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: Profile = Depends(get_current_user),
) -> ProfileResponse:
    """Return the currently authenticated user's profile."""
    return ProfileResponse.model_validate(current_user)
