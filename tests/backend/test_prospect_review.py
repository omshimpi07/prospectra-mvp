"""Tests for human review state machine, seller notes, rejection reasons, and isolation."""

from datetime import datetime, timezone
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
from backend.models.prospect import Prospect
from backend.models.workspace import WorkspaceMember
from backend.services.prospect import ProspectService


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
        email="seller@prospectra.test",
        full_name="Sarah Seller",
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


# ==============================================================================
# Service Level Review Tests
# ==============================================================================


@pytest.mark.anyio
async def test_review_prospect_approve_service(mock_db):
    """Test approving an unreviewed prospect sets review_status, reviewed_at, and reviewed_by."""
    ws_id = uuid4()
    prospect_id = uuid4()
    user_id = uuid4()

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        qualification_status="QUALIFIED",
        priority_score=0.85,
        review_status="UNREVIEWED",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = prospect
    mock_db.execute.return_value = mock_res

    updated = await ProspectService.review_prospect(
        db=mock_db,
        workspace_id=ws_id,
        prospect_id=prospect_id,
        reviewer_id=user_id,
        review_status="APPROVED",
        seller_note="High-value target with outdated mobile presence",
    )

    assert updated.review_status == "APPROVED"
    assert updated.rejection_reason is None
    assert updated.seller_note == "High-value target with outdated mobile presence"
    assert updated.reviewed_by == user_id
    assert updated.reviewed_at is not None
    # Correction 3: qualification_status must NOT be altered
    assert updated.qualification_status == "QUALIFIED"
    mock_db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_review_prospect_reject_requires_reason(mock_db):
    """Rejecting a prospect requires a valid rejection reason."""
    ws_id = uuid4()
    prospect_id = uuid4()
    user_id = uuid4()

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        qualification_status="QUALIFIED",
        priority_score=0.85,
        review_status="UNREVIEWED",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = prospect
    mock_db.execute.return_value = mock_res

    # Missing rejection reason
    with pytest.raises(Exception) as exc_info:
        await ProspectService.review_prospect(
            db=mock_db,
            workspace_id=ws_id,
            prospect_id=prospect_id,
            reviewer_id=user_id,
            review_status="REJECTED",
            rejection_reason="",
        )
    assert "rejection reason must be provided" in str(exc_info.value)


@pytest.mark.anyio
async def test_review_prospect_revert_from_rejected_clears_reason(mock_db):
    """Transitioning away from REJECTED back to APPROVED or UNREVIEWED clears rejection_reason."""
    ws_id = uuid4()
    prospect_id = uuid4()
    user_id = uuid4()

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        qualification_status="QUALIFIED",
        priority_score=0.85,
        review_status="REJECTED",
        rejection_reason="BAD_CONTACT_DATA",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = prospect
    mock_db.execute.return_value = mock_res

    # Revert to APPROVED
    updated = await ProspectService.review_prospect(
        db=mock_db,
        workspace_id=ws_id,
        prospect_id=prospect_id,
        reviewer_id=user_id,
        review_status="APPROVED",
    )

    assert updated.review_status == "APPROVED"
    assert updated.rejection_reason is None
    mock_db.commit.assert_awaited()


# ==============================================================================
# API Endpoint Review Tests
# ==============================================================================


def test_review_prospect_api_success(client, test_user, make_token, mock_db):
    """Test PATCH /{prospect_id}/review updates review state successfully."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    reviewed_prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Blue Tokai Coffee",
        canonical_category="cafe",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        fit_score=1.0,
        priority_score=0.92,
        review_status="APPROVED",
        rejection_reason=None,
        seller_note="Great prospect, valid email and phone available.",
        reviewed_by=test_user.id,
        reviewed_at=now,
        created_at=now,
        updated_at=now,
    )

    with patch(
        "backend.services.prospect.ProspectService.review_prospect", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = reviewed_prospect

        resp = client.patch(
            f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}/review",
            json={
                "review_status": "APPROVED",
                "seller_note": "Great prospect, valid email and phone available.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "APPROVED"
        assert data["rejection_reason"] is None
        assert data["seller_note"] == "Great prospect, valid email and phone available."
        assert data["reviewed_by"] == str(test_user.id)


def test_review_prospect_api_rejection_validation(client, test_user, make_token, mock_db):
    """Test rejecting via API without a rejection_reason fails with 422."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    resp = client.patch(
        f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}/review",
        json={
            "review_status": "REJECTED",
            # rejection_reason omitted!
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 422
    assert "rejection_reason is required" in resp.text


def test_review_prospect_api_tenant_isolation(client, test_user, make_token, mock_db):
    """User cannot review a prospect in a workspace they are not a member of."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    prospect_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = None  # Non-member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    resp = client.patch(
        f"/api/v1/workspaces/{ws_id}/prospects/{prospect_id}/review",
        json={"review_status": "APPROVED"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_list_prospects_filter_by_review_status(client, test_user, make_token, mock_db):
    """GET /prospects?review_status=UNREVIEWED passes the filter to query."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_list_res]

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/prospects?review_status=UNREVIEWED",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    mock_db.execute.assert_awaited()
    # Check that stmt included review_status
    last_call = mock_db.execute.call_args[0][0]
    query_str = str(last_call.compile(compile_kwargs={"literal_binds": True}))
    assert "prospects.review_status = 'UNREVIEWED'" in query_str
