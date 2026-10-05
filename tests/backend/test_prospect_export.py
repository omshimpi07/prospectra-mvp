"""Tests for CSV export, formula injection defense, filtering, and tenant isolation."""

import csv
from datetime import datetime, timezone
import io
from unittest.mock import AsyncMock, MagicMock
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
# Service Level Export Tests
# ==============================================================================


@pytest.mark.anyio
async def test_export_prospects_csv_defaults_to_approved(mock_db):
    """Correction 6: Default export must filter review_status = 'APPROVED'."""
    ws_id = uuid4()
    now = datetime.now(timezone.utc)

    p1 = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Artisan Cafe",
        canonical_category="cafe",
        city="Pune",
        website_url="https://artisancafe.example.com",
        phone="+919876543210",
        qualification_status="QUALIFIED",
        priority_score=0.88,
        score_breakdown={"scoring_profile": "WEB_REDESIGN_MODERNIZATION"},
        review_status="APPROVED",
        qualification_reason="Valid website, lacks mobile viewport.",
        raw_signals={"public_emails": ["info@artisancafe.example.com"]},
        created_at=now,
        updated_at=now,
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [p1]
    mock_db.execute.return_value = mock_res

    csv_text, filename = await ProspectService.export_prospects_csv(
        db=mock_db,
        workspace_id=ws_id,
        # review_status not provided -> defaults to 'APPROVED'
    )

    mock_db.execute.assert_awaited_once()
    stmt = mock_db.execute.call_args[0][0]
    query_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "prospects.review_status = 'APPROVED'" in query_str
    assert "approved" in filename

    # Verify CSV content
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 2  # header + 1 row
    assert rows[0][0] == "Business Name"
    assert rows[0][4] == "Priority Score"
    assert rows[1][0] == "Artisan Cafe"
    assert rows[1][4] == "0.88"
    assert rows[1][7] == "APPROVED"
    assert rows[1][9] == "info@artisancafe.example.com"


@pytest.mark.anyio
async def test_export_prospects_csv_formula_injection_defense(mock_db):
    """Cells beginning with =, +, -, @, \\t, \\r must be prepended with ' to protect spreadsheet applications."""
    ws_id = uuid4()
    now = datetime.now(timezone.utc)

    adversarial_prospect = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="=cmd|' /C calc'!A0",  # Formula injection attempt
        canonical_category="+Malicious Category",
        city="-Pune",
        website_url="@https://evil.example.com",
        phone="+919876543210",
        qualification_status="QUALIFIED",
        priority_score=0.95,
        review_status="APPROVED",
        seller_note='=HYPERLINK("http://phishing.example.com", "Click Here")',
        created_at=now,
        updated_at=now,
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [adversarial_prospect]
    mock_db.execute.return_value = mock_res

    csv_text, _ = await ProspectService.export_prospects_csv(
        db=mock_db,
        workspace_id=ws_id,
        review_status="APPROVED",
    )

    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    data_row = rows[1]

    # Verify prepended single-quotes
    assert data_row[0] == "'=cmd|' /C calc'!A0"
    assert data_row[1] == "'+Malicious Category"
    assert data_row[2] == "'-Pune"
    assert data_row[3] == "'@https://evil.example.com"
    assert data_row[12] == '\'=HYPERLINK("http://phishing.example.com", "Click Here")'


# ==============================================================================
# API Level Export Tests
# ==============================================================================


def test_export_api_success_and_route_order(client, test_user, make_token, mock_db):
    """Verify GET /export is invoked cleanly and not intercepted by /{prospect_id}."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="owner")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    mock_db_res = MagicMock()
    mock_db_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_db_res]

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/prospects/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert "Business Name,Canonical Category,City,Website" in resp.text


def test_export_api_tenant_isolation(client, test_user, make_token, mock_db):
    """Non-member cannot trigger CSV export."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = None  # Non-member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/prospects/export",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
