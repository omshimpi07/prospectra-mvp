"""Tests for Prospect Rescoring, Multi-ICP scoring, ranking queries, and rescore API."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.auth.dependencies import get_jwt_verifier
from backend.config import get_settings
from backend.database import get_db
from backend.main import create_app
from backend.models.base import utc_now
from backend.models.icp import ICP
from backend.models.profile import Profile
from backend.models.prospect import Prospect
from backend.models.workspace import WorkspaceMember
from backend.schemas.icp import CompiledICPCriteria
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


# ==============================================================================
# 1. Multi-ICP Rescoring Tests
# ==============================================================================


@pytest.mark.anyio
async def test_rescore_workspace_prospects_multi_icp(mock_db):
    """Test that prospects under different ICPs in the same workspace are rescored with their own ICP's profile."""
    ws_id = uuid4()
    user_id = uuid4()

    icp_a_id = uuid4()
    icp_b_id = uuid4()

    # ICP A: Web Design (Resolves to WEB_REDESIGN_MODERNIZATION)
    criteria_a = CompiledICPCriteria(
        service_offering="Custom Website Redesign & Modernization",
        target_categories=["restaurant", "cafe"],
        location={"city": "Pune", "country": "India"},
        signals={"has_website": True},
        qualification_notes=["Target outdated sites needing mobile responsiveness"],
    )
    icp_a = ICP(
        id=icp_a_id,
        workspace_id=ws_id,
        created_by=user_id,
        name="Web Design ICP",
        raw_prompt="Restaurants needing web design",
        status="APPROVED",
        compiled_criteria=criteria_a.model_dump(),
    )

    # ICP B: SEO & Content (Resolves to MARKETING_AND_SEO)
    criteria_b = CompiledICPCriteria(
        service_offering="Search Engine Optimization & Local Marketing",
        target_categories=["clinic", "dental"],
        location={"city": "Mumbai", "country": "India"},
        signals={"has_website": True},
        qualification_notes=["Target clinics with fast sites needing search ranking"],
    )
    icp_b = ICP(
        id=icp_b_id,
        workspace_id=ws_id,
        created_by=user_id,
        name="SEO & Marketing ICP",
        raw_prompt="Clinics needing SEO",
        status="APPROVED",
        compiled_criteria=criteria_b.model_dump(),
    )

    # Prospect 1 under ICP A: Outdated site (mobile viewport missing) -> Very high gap score for web redesign
    p1 = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=icp_a_id,
        name="Retro Cafe",
        canonical_category="cafe",
        website_url="https://retrocafe.example.com",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        raw_signals={
            "reachable": True,
            "http_status": 200,
            "ssl_valid": True,
            "ssl_days_remaining": 60,
            "mobile_viewport": False,  # Massive gap in web redesign
            "page_speed_tier": "poor",
            "html_size_bytes": 800000,
        },
    )

    # Prospect 2 under ICP B: Clinic with modern technical baseline -> Very high score for SEO
    p2 = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=icp_b_id,
        name="Metro Dental Clinic",
        canonical_category="clinic",
        website_url="https://metrodental.example.com",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        raw_signals={
            "reachable": True,
            "http_status": 200,
            "ssl_valid": True,
            "ssl_days_remaining": 120,
            "mobile_viewport": True,
            "page_speed_tier": "fast",
            "html_size_bytes": 45000,
        },
    )

    # 1st execute: load prospects
    mock_prospects_res = MagicMock()
    mock_prospects_res.scalars.return_value.all.return_value = [p1, p2]

    # 2nd execute: load ICPs
    mock_icps_res = MagicMock()
    mock_icps_res.scalars.return_value.all.return_value = [icp_a, icp_b]

    mock_db.execute.side_effect = [mock_prospects_res, mock_icps_res]

    res = await ProspectService.rescore_workspace_prospects(db=mock_db, workspace_id=ws_id)

    assert res.rescored_count == 2
    mock_db.commit.assert_awaited_once()

    # Verify p1 was scored using WEB_REDESIGN_MODERNIZATION
    assert p1.score_breakdown["scoring_profile"] == "WEB_REDESIGN_MODERNIZATION"
    assert p1.scoring_version == "v1.0"
    assert p1.scored_at is not None
    assert 0.0 <= p1.priority_score <= 1.0
    # In web redesign, missing mobile viewport yields 0.25 gap score
    factor_labels_p1 = [f["label"] for f in p1.score_breakdown["factors"]]
    assert "Lacks Mobile Viewport" in factor_labels_p1

    # Verify p2 was scored using MARKETING_AND_SEO
    assert p2.score_breakdown["scoring_profile"] == "MARKETING_AND_SEO"
    assert p2.scoring_version == "v1.0"
    assert p2.scored_at is not None
    assert 0.0 <= p2.priority_score <= 1.0
    factor_labels_p2 = [f["label"] for f in p2.score_breakdown["factors"]]
    assert "Mobile & Security Foundation" in factor_labels_p2


@pytest.mark.anyio
async def test_rescore_empty_workspace(mock_db):
    """Rescoring a workspace with no prospects returns 0 count cleanly."""
    ws_id = uuid4()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    res = await ProspectService.rescore_workspace_prospects(db=mock_db, workspace_id=ws_id)
    assert res.rescored_count == 0
    assert "No prospects found" in res.message


# ==============================================================================
# 2. Deterministic Ranking & Query Ordering
# ==============================================================================


@pytest.mark.anyio
async def test_list_prospects_deterministic_ranking_query(mock_db):
    """Verify that list_prospects issues SQL query with the deterministic 4-tier ranking."""
    ws_id = uuid4()

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    await ProspectService.list_prospects(
        db=mock_db,
        workspace_id=ws_id,
        qualification_status="QUALIFIED",
        min_score=0.65,
        limit=20,
        offset=0,
    )

    mock_db.execute.assert_awaited_once()
    stmt = mock_db.execute.call_args[0][0]
    query_str = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    # Check workspace tenant boundary (supports hex or hyphenated UUID)
    assert (str(ws_id) in query_str) or (ws_id.hex in query_str)
    # Check status filter
    assert "prospects.qualification_status = 'QUALIFIED'" in query_str
    # Check min_score filter
    assert "prospects.priority_score >= 0.65" in query_str
    # Check deterministic ORDER BY sequence
    assert "ORDER BY prospects.priority_score DESC NULLS LAST" in query_str
    assert "CASE WHEN (prospects.qualification_status = 'QUALIFIED') THEN 1" in query_str
    assert "prospects.created_at DESC" in query_str
    assert "prospects.id ASC" in query_str


# ==============================================================================
# 3. API Endpoint Tests (POST /rescore and dynamic route safety)
# ==============================================================================


def test_rescore_api_unauthorized(client):
    """Unauthenticated rescore request must be rejected with 401."""
    ws_id = uuid4()
    resp = client.post(f"/api/v1/workspaces/{ws_id}/prospects/rescore")
    assert resp.status_code == 401


def test_rescore_api_non_member_forbidden(client, test_user, make_token, mock_db):
    """Non-member cannot trigger rescore in workspace."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = None  # Non-member

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res]

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/prospects/rescore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_rescore_api_success(client, test_user, make_token, mock_db):
    """Verify POST /rescore route is invoked cleanly without route collision with /{prospect_id}."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="owner")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    # Empty prospects query for rescore
    mock_prospects_res = MagicMock()
    mock_prospects_res.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_prospects_res]

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/prospects/rescore",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Must return 200 OK (NOT 422 due to UUID validation on /{prospect_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["rescored_count"] == 0
    assert "No prospects found" in data["message"]


def test_list_prospects_api_min_score_filter(client, test_user, make_token, mock_db):
    """Verify GET /prospects with min_score filter serializes score_breakdown properly."""
    token = make_token(sub=str(test_user.id), email=test_user.email)
    ws_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = test_user

    member = WorkspaceMember(id=uuid4(), workspace_id=ws_id, user_id=test_user.id, role="member")
    mock_mem_res = MagicMock()
    mock_mem_res.scalar_one_or_none.return_value = member

    prospect = Prospect(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        name="Top Tier Cafe",
        canonical_category="cafe",
        status="COMPLETED",
        qualification_status="QUALIFIED",
        fit_score=1.0,
        priority_score=0.88,
        score_breakdown={
            "raw_score": 0.88,
            "status_multiplier": 1.0,
            "priority_score": 0.88,
            "scoring_profile": "WEB_REDESIGN_MODERNIZATION",
            "scoring_version": "v1.0",
            "scored_at": now.isoformat(),
            "factors": [
                {
                    "key": "mobile_viewport_gap",
                    "label": "Lacks Mobile Viewport",
                    "impact": 0.25,
                    "max_impact": 0.25,
                    "status": "matched",
                    "evidence_snippet": "Mobile viewport tag absent",
                }
            ],
        },
        scoring_version="v1.0",
        scored_at=now,
        created_at=now,
        updated_at=now,
    )

    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [prospect]

    mock_db.execute.side_effect = [mock_user_res, mock_mem_res, mock_list_res]

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/prospects?min_score=0.8",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    p = items[0]
    assert p["name"] == "Top Tier Cafe"
    assert p["priority_score"] == 0.88
    assert p["score_breakdown"]["scoring_profile"] == "WEB_REDESIGN_MODERNIZATION"
    assert len(p["score_breakdown"]["factors"]) == 1
    assert p["scoring_version"] == "v1.0"
