"""Integration tests for Searches API endpoints."""

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
from backend.models.search import Search, SearchResult
from backend.models.workspace import WorkspaceMember
from backend.providers.discovery.factory import get_discovery_provider
from backend.providers.discovery.mock import MockDiscoveryProvider


def make_sample_search(
    workspace_id: UUID,
    user_id: UUID,
    search_id: UUID | None = None,
    icp_id: UUID | None = None,
    status: str = "CREATED",
) -> Search:
    now = utc_now()
    return Search(
        id=search_id or uuid4(),
        workspace_id=workspace_id,
        icp_id=icp_id or uuid4(),
        created_by=user_id,
        status=status,
        specification={
            "target_categories": ["cafe"],
            "city": "Pune",
            "center_lat": 18.5204,
            "center_lon": 73.8567,
            "radius_km": 25.0,
            "bounding_box": {
                "min_lat": 18.29,
                "max_lat": 18.75,
                "min_lon": 73.62,
                "max_lon": 74.09,
            },
            "limit": 100,
        },
        total_candidates=0,
        new_candidates=0,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
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
def mock_discovery():
    return MockDiscoveryProvider()


@pytest.fixture
def client(mock_db, test_user, mock_verifier, test_settings, mock_discovery):
    app = create_app()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_jwt_verifier] = lambda: mock_verifier
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_discovery_provider] = lambda: mock_discovery

    with TestClient(app) as test_client:
        yield test_client


def test_create_search_unauthorized(client):
    ws_id = uuid4()
    response = client.post(
        f"/api/v1/workspaces/{ws_id}/searches",
        json={"icp_id": str(uuid4())},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_create_search_success(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    icp_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    now = utc_now()
    approved_icp = ICP(
        id=icp_id,
        workspace_id=ws_id,
        created_by=test_user.id,
        name="Pune Cafes Approved",
        raw_prompt="prompt",
        status="APPROVED",
        compiled_criteria={
            "target_categories": ["cafe"],
            "location": {"city": "Pune"},
        },
        created_at=now,
        updated_at=now,
    )
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one_or_none.return_value = approved_icp

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_icp_res]

    response = client.post(
        f"/api/v1/workspaces/{ws_id}/searches",
        headers={"Authorization": f"Bearer {token}"},
        json={"icp_id": str(icp_id), "radius_km": 20.0, "limit": 50},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "CREATED"
    assert data["icp_id"] == str(icp_id)
    assert data["workspace_id"] == str(ws_id)
    assert data["specification"]["city"] == "Pune"


def test_list_searches_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    sample_search = make_sample_search(ws_id, test_user.id)
    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [sample_search]

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_list_res]

    response = client.get(
        f"/api/v1/workspaces/{ws_id}/searches",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(sample_search.id)


def test_get_search_endpoint_and_isolation(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    search_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    sample_search = make_sample_search(ws_id, test_user.id, search_id=search_id)
    mock_search_res = MagicMock()
    mock_search_res.scalar_one_or_none.return_value = sample_search

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_search_res]

    response = client.get(
        f"/api/v1/workspaces/{ws_id}/searches/{search_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(search_id)

    # Cross-workspace check: not found in target workspace -> 404
    mock_none_res = MagicMock()
    mock_none_res.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_none_res]

    response404 = client.get(
        f"/api/v1/workspaces/{ws_id}/searches/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response404.status_code == 404
    assert response404.json()["error"]["code"] == "NOT_FOUND"


def test_run_search_endpoint_queues_job(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    search_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    search = make_sample_search(ws_id, test_user.id, search_id=search_id, status="CREATED")
    mock_search_res = MagicMock()
    mock_search_res.scalar_one_or_none.return_value = search

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_search_res]

    response = client.post(
        f"/api/v1/workspaces/{ws_id}/searches/{search_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["queued_at"] is not None


def test_get_search_results_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    search_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    search = make_sample_search(ws_id, test_user.id, search_id=search_id, status="COMPLETED")
    mock_search_res = MagicMock()
    mock_search_res.scalar_one_or_none.return_value = search

    now = utc_now()
    result_item = SearchResult(
        id=uuid4(),
        search_id=search_id,
        workspace_id=ws_id,
        external_id="place_123",
        provider="overture",
        name="Blue Tokai Coffee",
        canonical_category="cafe",
        latitude=18.5362,
        longitude=73.8941,
        address="Koregaon Park, Pune",
        city="Pune",
        confidence=0.95,
        created_at=now,
    )
    mock_results_res = MagicMock()
    mock_results_res.scalars.return_value.all.return_value = [result_item]

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_search_res, mock_results_res]

    response = client.get(
        f"/api/v1/workspaces/{ws_id}/searches/{search_id}/results",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Blue Tokai Coffee"
    assert data[0]["canonical_category"] == "cafe"


def test_physical_delete_search_rejected_405(client, test_user, make_token):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    search_id = uuid4()

    response = client.delete(
        f"/api/v1/workspaces/{ws_id}/searches/{search_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 405
