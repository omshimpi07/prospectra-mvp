"""Integration tests for ICP API endpoints."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_jwt_verifier
from backend.config import get_settings
from backend.database import get_db
from backend.main import create_app
from backend.models.base import utc_now
from backend.models.icp import ICP
from backend.models.profile import Profile
from backend.models.workspace import WorkspaceMember
from backend.providers.ai.factory import get_ai_provider
from backend.providers.ai.mock import MockAIProvider, get_default_mock_criteria


def make_sample_icp(
    workspace_id: UUID,
    user_id: UUID,
    icp_id: UUID | None = None,
    name: str = "Sample ICP",
    raw_prompt: str = "Sample prompt",
    status: str = "DRAFT",
    version: int = 1,
    compiled_criteria: dict | None = None,
) -> ICP:
    now = utc_now()
    return ICP(
        id=icp_id or uuid4(),
        workspace_id=workspace_id,
        created_by=user_id,
        name=name,
        raw_prompt=raw_prompt,
        status=status,
        version=version,
        compiled_criteria=compiled_criteria,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def test_user():
    now = utc_now()
    return Profile(
        id=uuid4(),
        email="founder@prospectra.test",
        full_name="Alex Founder",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_ai():
    return MockAIProvider(default_criteria=get_default_mock_criteria(city="Pune"))


@pytest.fixture
def client(mock_db, test_user, mock_verifier, test_settings, mock_ai):
    app = create_app()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_jwt_verifier] = lambda: mock_verifier
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_ai_provider] = lambda: mock_ai

    with TestClient(app) as test_client:
        yield test_client


def test_create_icp_unauthorized(client):
    ws_id = uuid4()
    response = client.post(
        f"/api/v1/workspaces/{ws_id}/icps",
        json={"name": "Test ICP", "raw_prompt": "Targeting cafes in Pune"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_icp_non_member_returns_404(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    # 1. get_current_user lookup
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    # 2. require_workspace_member lookup -> None (non-member)
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    response = client.post(
        f"/api/v1/workspaces/{ws_id}/icps",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test ICP", "raw_prompt": "Targeting cafes in Pune"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_create_icp_success(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    # 1. get_current_user
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    # 2. require_workspace_member -> member
    member = WorkspaceMember(
        id=uuid4(),
        workspace_id=ws_id,
        user_id=test_user.id,
        role="member",
    )
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    response = client.post(
        f"/api/v1/workspaces/{ws_id}/icps",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Pune Cafes Lead Engine",
            "raw_prompt": "I build modern websites for bakeries and cafes in Pune without a website.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pune Cafes Lead Engine"
    assert data["status"] == "DRAFT"
    assert data["version"] == 1
    assert data["workspace_id"] == str(ws_id)
    assert data["created_by"] == str(test_user.id)


def test_list_icps_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    sample_icp = make_sample_icp(
        workspace_id=ws_id,
        user_id=test_user.id,
        name="Listed ICP",
    )
    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [sample_icp]

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_list_res]

    response = client.get(
        f"/api/v1/workspaces/{ws_id}/icps?status=DRAFT",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Listed ICP"


def test_get_icp_endpoint_and_cross_workspace_isolation(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    # 1. Successful get
    sample_icp = make_sample_icp(
        workspace_id=ws_id,
        user_id=test_user.id,
        icp_id=icp_id,
        name="Target ICP",
    )
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one_or_none.return_value = sample_icp

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_icp_res]

    response = client.get(
        f"/api/v1/workspaces/{ws_id}/icps/{icp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(icp_id)

    # 2. Cross-workspace / Not Found check -> 404
    mock_db.execute.side_effect = None
    mock_none_res = MagicMock()
    mock_none_res.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_none_res]

    response404 = client.get(
        f"/api/v1/workspaces/{ws_id}/icps/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response404.status_code == 404
    assert response404.json()["error"]["code"] == "NOT_FOUND"


def test_patch_icp_member_cannot_archive_403(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    sample_icp = make_sample_icp(
        workspace_id=ws_id,
        user_id=test_user.id,
        icp_id=icp_id,
        name="Target ICP",
        status="APPROVED",
    )
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one_or_none.return_value = sample_icp

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_icp_res]

    response = client.patch(
        f"/api/v1/workspaces/{ws_id}/icps/{icp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "ARCHIVED"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_OPERATION"


def test_patch_icp_owner_can_archive_200(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    owner = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="owner")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = owner

    sample_icp = make_sample_icp(
        workspace_id=ws_id,
        user_id=test_user.id,
        icp_id=icp_id,
        name="Target ICP",
        status="APPROVED",
    )
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one_or_none.return_value = sample_icp

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_icp_res]

    response = client.patch(
        f"/api/v1/workspaces/{ws_id}/icps/{icp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "ARCHIVED"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"


def test_compile_icp_endpoint_success(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    sample_icp = make_sample_icp(
        workspace_id=ws_id,
        user_id=test_user.id,
        icp_id=icp_id,
        name="Draft ICP",
        raw_prompt="I build modern websites for bakeries and cafes in Pune without a website.",
        status="DRAFT",
    )
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one_or_none.return_value = sample_icp

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_icp_res]

    response = client.post(
        f"/api/v1/workspaces/{ws_id}/icps/{icp_id}/compile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPILED"
    assert data["version"] == 2
    assert data["compiled_criteria"]["location"]["city"] == "Pune"


def test_physical_delete_icp_rejected(client, test_user, make_token):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    # Attempt physical DELETE on the route
    response = client.delete(
        f"/api/v1/workspaces/{ws_id}/icps/{icp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 405
