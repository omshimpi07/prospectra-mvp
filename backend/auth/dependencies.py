"""FastAPI authentication and authorization dependencies."""

from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.jwt import SupabaseJWTVerifier, get_jwt_verifier
from backend.config import Settings, get_settings
from backend.database import get_db
from backend.middleware.errors import AppError
from backend.models.profile import Profile
from backend.models.workspace import WorkspaceMember

oauth2_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    verifier: SupabaseJWTVerifier = Depends(get_jwt_verifier),
) -> Profile:
    """Validate JWT and retrieve authenticated user's profile.

    Does NOT lazily create a profile: the database trigger on auth.users is authoritative.
    Missing profile is treated as a 404 consistency error.
    """
    if credentials is None or not credentials.credentials:
        raise AppError("UNAUTHORIZED", "Missing authentication token", status_code=401)

    payload = verifier.verify_token(credentials.credentials, settings=settings)
    user_id = UUID(str(payload["sub"]))

    stmt = select(Profile).where(Profile.id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile is None:
        raise AppError(
            "PROFILE_NOT_FOUND",
            "User profile not found. Ensure signup trigger completed.",
            status_code=404,
        )

    return profile


def require_workspace_member(
    required_role: str | None = None,
) -> Callable[..., Coroutine[Any, Any, WorkspaceMember]]:
    """Dependency factory verifying membership in the target workspace.

    Returns 404 if workspace or membership not found to prevent tenant enumeration.
    Returns 403 if user lacks required role (e.g. owner).
    """

    async def _dependency(
        workspace_id: UUID,
        current_user: Profile = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        member = result.scalar_one_or_none()

        if member is None:
            raise AppError("NOT_FOUND", "Workspace not found", status_code=404)

        if required_role == "owner" and member.role != "owner":
            raise AppError("FORBIDDEN", "Owner permission required", status_code=403)

        return member

    return _dependency
