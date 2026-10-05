"""Integration tests for Profiles and Workspaces API endpoints."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_jwt_verifier
from backend.config import get_settings
from backend.database import get_db
from backend.main import create_app
from backend.models.base import utc_now
from backend.models.profile import Profile
from backend.models.workspace import Workspace, WorkspaceMember


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def test_user():
    now = utc_now()
    return Profile(
        id=uuid4(),
        email="tester@example.com",
        full_name="Test User",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def client(mock_db, test_user, mock_verifier, test_settings):
    app = create_app()

    # Override dependencies
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_jwt_verifier] = lambda: mock_verifier
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"
    assert "status" in data
    assert "database" in data


def test_get_my_profile_unauthenticated(client):
    response = client.get("/api/v1/profiles/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_get_my_profile_authenticated(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)

    # Mock DB query for get_current_user
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = test_user
    mock_db.execute.return_value = mock_res

    response = client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["email"] == test_user.email


def test_create_workspace_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)

    # 1. get_current_user lookup
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    # 2. Workspace slug uniqueness check
    mock_slug_res = MagicMock()
    mock_slug_res.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_user_res, mock_slug_res]

    response = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Alpha Growth"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alpha Growth"
    assert data["slug"] == "alpha-growth"
    assert data["role"] == "owner"


def test_get_workspace_non_member_returns_404(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    target_ws_id = uuid4()

    # 1. get_current_user
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    # 2. require_workspace_member check -> returns None (not a member)
    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_user_res, mock_member_res]

    response = client.get(
        f"/api/v1/workspaces/{target_ws_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_get_workspace_member_success(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    target_ws_id = uuid4()
    now = utc_now()

    ws = Workspace(
        id=target_ws_id,
        name="Valid WS",
        slug="valid-ws",
        created_by=test_user.id,
        created_at=now,
        updated_at=now,
    )
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=target_ws_id,
        user_id=test_user.id,
        role="owner",
        joined_at=now,
    )

    # 1. get_current_user
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    # 2. require_workspace_member check
    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = member

    # 3. get_workspace_by_id service query
    mock_ws_res = MagicMock()
    mock_ws_res.first.return_value = (ws, "owner")

    mock_db.execute.side_effect = [mock_user_res, mock_member_res, mock_ws_res]

    response = client.get(
        f"/api/v1/workspaces/{target_ws_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(target_ws_id)
    assert data["name"] == "Valid WS"
    assert data["role"] == "owner"
