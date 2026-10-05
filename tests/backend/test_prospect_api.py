"""API tests for Prospect intelligence and qualification endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.auth.dependencies import get_jwt_verifier
from backend.config import get_settings
from backend.database import get_db
from backend.main import create_app
from backend.models.base import utc_now
from backend.models.profile import Profile
from backend.models.prospect import Prospect, QualificationEvidence
from backend.models.workspace import WorkspaceMember
from backend.schemas.prospect import QualifyCandidatesResponse


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
def client(mock_db, test_user, mock_verifier, test_settings):
    app = create_app()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_jwt_verifier] = lambda: mock_verifier
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client


def test_qualify_candidates_unauthorized(client):
    ws_id = uuid4()
    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/prospects/qualify-candidates",
        json={"search_result_ids": [str(uuid4())]},
    )
    assert resp.status_code == 401


def test_qualify_candidates_non_member_returns_404(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = None  # Not a member!

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/prospects/qualify-candidates",
        json={"search_result_ids": [str(uuid4())]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_qualify_candidates_success(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    cand_id = uuid4()
    prospect_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="owner")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    mock_resp = QualifyCandidatesResponse(
        enqueued_count=1,
        prospect_ids=[prospect_id],
        message="Enqueued 1 candidate(s) for qualification research.",
    )

    with patch(
        "backend.services.prospect.ProspectService.qualify_candidates", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = mock_resp

        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/prospects/qualify-candidates",
            json={"search_result_ids": [str(cand_id)]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["enqueued_count"] == 1
        assert data["prospect_ids"] == [str(prospect_id)]


def test_list_prospects_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    now = utc_now()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    prospect = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        fit_score=1.0,
        qualification_reason="Qualified: Valid website with mobile viewport.",
        created_at=now,
        updated_at=now,
    )

    with patch(
        "backend.services.prospect.ProspectService.list_prospects", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = [prospect]

        resp = client.get(
            f"/api/v1/workspaces/{ws_id}/prospects?qualification_status=QUALIFIED",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Artisan Cafe"
        assert data[0]["qualification_status"] == "QUALIFIED"


def test_get_prospect_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()
    now = utc_now()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        fit_score=1.0,
        created_at=now,
        updated_at=now,
    )

    with patch(
        "backend.services.prospect.ProspectService.get_prospect_by_id", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = prospect

        resp = client.get(
            f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(prospect_id)


def test_get_prospect_evidence_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()
    now = utc_now()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    evidence = QualificationEvidence(
        id=uuid4(),
        workspace_id=ws_id,
        prospect_id=prospect_id,
        signal_key="web_reachability",
        signal_value={"reachable": True, "http_status": 200},
        confidence=1.0,
        source_url="https://artisancafe.example.com",
        observed_at=now,
        created_at=now,
    )

    with patch(
        "backend.services.prospect.ProspectService.list_evidence", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = [evidence]

        resp = client.get(
            f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}/evidence",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["signal_key"] == "web_reachability"


def test_requalify_prospect_endpoint(client, test_user, make_token, mock_db):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()
    now = utc_now()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        status="QUEUED",
        qualification_status="UNQUALIFIED",
        fit_score=0.0,
        created_at=now,
        updated_at=now,
    )

    with patch(
        "backend.services.prospect.ProspectService.requalify_prospect", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = prospect

        resp = client.post(
            f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}/requalify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "QUEUED"


def test_physical_delete_prospect_rejected_405(client, test_user, make_token):
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()
    resp = client.delete(
        f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 405
