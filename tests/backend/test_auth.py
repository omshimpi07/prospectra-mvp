"""Unit tests for JWT verification and auth dependencies."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth.dependencies import get_current_user, require_workspace_member
from backend.middleware.errors import AppError
from backend.models.profile import Profile
from backend.models.workspace import WorkspaceMember


def test_verify_valid_token(mock_verifier, make_token, test_settings):
    user_id = str(uuid4())
    token = make_token(sub=user_id, email="user@example.com")
    payload = mock_verifier.verify_token(token, settings=test_settings)
    assert payload["sub"] == user_id
    assert payload["email"] == "user@example.com"
    assert payload["aud"] == "authenticated"


def test_verify_expired_token(mock_verifier, make_token, test_settings):
    token = make_token(exp_delta=-60)
    with pytest.raises(AppError) as exc_info:
        mock_verifier.verify_token(token, settings=test_settings)
    assert exc_info.value.code == "TOKEN_EXPIRED"
    assert exc_info.value.status_code == 401


def test_verify_invalid_issuer(mock_verifier, make_token, test_settings):
    token = make_token(issuer="https://evil.attacker.com/auth/v1")
    with pytest.raises(AppError) as exc_info:
        mock_verifier.verify_token(token, settings=test_settings)
    assert exc_info.value.code == "INVALID_ISSUER"
    assert exc_info.value.status_code == 401


def test_verify_invalid_audience(mock_verifier, make_token, test_settings):
    token = make_token(audience="wrong-audience")
    with pytest.raises(AppError) as exc_info:
        mock_verifier.verify_token(token, settings=test_settings)
    assert exc_info.value.code == "INVALID_AUDIENCE"
    assert exc_info.value.status_code == 401


def test_verify_invalid_sub_uuid(mock_verifier, make_token, test_settings):
    token = make_token(sub="not-a-valid-uuid")
    with pytest.raises(AppError) as exc_info:
        mock_verifier.verify_token(token, settings=test_settings)
    assert exc_info.value.code == "INVALID_TOKEN"
    assert exc_info.value.status_code == 401


def test_verify_hs256_fallback(mock_verifier, make_token, test_settings):
    token = make_token(algorithm="HS256")
    payload = mock_verifier.verify_token(token, settings=test_settings)
    assert payload["aud"] == "authenticated"


def test_get_current_user_missing_credentials(mock_verifier, test_settings):
    mock_db = AsyncMock()
    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            get_current_user(
                credentials=None,
                db=mock_db,
                settings=test_settings,
                verifier=mock_verifier,
            )
        )
    assert exc_info.value.code == "UNAUTHORIZED"
    assert exc_info.value.status_code == 401


def test_get_current_user_profile_not_found(mock_verifier, make_token, test_settings):
    user_id = uuid4()
    token = make_token(sub=str(user_id))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(AppError) as exc_info:
        asyncio.run(
            get_current_user(
                credentials=credentials,
                db=mock_db,
                settings=test_settings,
                verifier=mock_verifier,
            )
        )
    assert exc_info.value.code == "PROFILE_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_get_current_user_success(mock_verifier, make_token, test_settings):
    user_id = uuid4()
    token = make_token(sub=str(user_id))
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    mock_db = AsyncMock()
    expected_profile = Profile(id=user_id, email="test@example.com")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = expected_profile
    mock_db.execute.return_value = mock_result

    profile = asyncio.run(
        get_current_user(
            credentials=credentials,
            db=mock_db,
            settings=test_settings,
            verifier=mock_verifier,
        )
    )
    assert profile.id == user_id


def test_require_workspace_member_not_found():
    workspace_id = uuid4()
    current_user = Profile(id=uuid4(), email="user@example.com")
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    dep = require_workspace_member()
    with pytest.raises(AppError) as exc_info:
        asyncio.run(dep(workspace_id=workspace_id, current_user=current_user, db=mock_db))
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_require_workspace_member_forbidden_role():
    workspace_id = uuid4()
    current_user = Profile(id=uuid4(), email="user@example.com")
    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=current_user.id, role="member")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_member
    mock_db.execute.return_value = mock_result

    dep = require_workspace_member(required_role="owner")
    with pytest.raises(AppError) as exc_info:
        asyncio.run(dep(workspace_id=workspace_id, current_user=current_user, db=mock_db))
    assert exc_info.value.code == "FORBIDDEN"
    assert exc_info.value.status_code == 403
