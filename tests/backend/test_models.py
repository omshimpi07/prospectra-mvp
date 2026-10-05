"""Tests for SQLAlchemy models."""

from uuid import uuid4

from backend.models.profile import Profile
from backend.models.workspace import Workspace, WorkspaceMember


def test_profile_model_instantiation():
    user_id = uuid4()
    profile = Profile(id=user_id, email="alex@example.com", full_name="Alex Smith")
    assert profile.id == user_id
    assert profile.email == "alex@example.com"
    assert profile.full_name == "Alex Smith"
    assert Profile.__tablename__ == "profiles"


def test_workspace_model_instantiation():
    ws_id = uuid4()
    creator_id = uuid4()
    workspace = Workspace(
        id=ws_id,
        name="Acme Agency",
        slug="acme-agency",
        created_by=creator_id,
    )
    assert workspace.id == ws_id
    assert workspace.name == "Acme Agency"
    assert workspace.slug == "acme-agency"
    assert workspace.created_by == creator_id
    assert Workspace.__tablename__ == "workspaces"


def test_workspace_member_model_instantiation():
    member_id = uuid4()
    ws_id = uuid4()
    user_id = uuid4()
    member = WorkspaceMember(
        id=member_id,
        workspace_id=ws_id,
        user_id=user_id,
        role="owner",
    )
    assert member.id == member_id
    assert member.workspace_id == ws_id
    assert member.user_id == user_id
    assert member.role == "owner"
    assert WorkspaceMember.__tablename__ == "workspace_members"


def test_icp_model_instantiation():
    from backend.models.icp import ICP

    icp_id = uuid4()
    ws_id = uuid4()
    user_id = uuid4()
    icp = ICP(
        id=icp_id,
        workspace_id=ws_id,
        created_by=user_id,
        name="Pune Bakery Leads",
        raw_prompt="Targeting bakeries in Pune",
        status="DRAFT",
        version=1,
    )
    assert icp.id == icp_id
    assert icp.workspace_id == ws_id
    assert icp.created_by == user_id
    assert icp.name == "Pune Bakery Leads"
    assert icp.status == "DRAFT"
    assert icp.version == 1
    assert ICP.__tablename__ == "icps"


def test_search_and_result_models_instantiation():
    from backend.models.search import Search, SearchResult

    search_id = uuid4()
    ws_id = uuid4()
    icp_id = uuid4()
    user_id = uuid4()

    search = Search(
        id=search_id,
        workspace_id=ws_id,
        icp_id=icp_id,
        created_by=user_id,
        status="CREATED",
        specification={"city": "Pune"},
    )
    assert search.id == search_id
    assert search.status == "CREATED"
    assert Search.__tablename__ == "searches"

    res_id = uuid4()
    result = SearchResult(
        id=res_id,
        search_id=search_id,
        workspace_id=ws_id,
        external_id="ext-123",
        provider="overture",
        name="Blue Tokai Coffee",
        canonical_category="cafe",
        latitude=18.5362,
        longitude=73.8941,
    )
    assert result.id == res_id
    assert result.external_id == "ext-123"
    assert SearchResult.__tablename__ == "search_results"


def test_prospect_and_evidence_models_instantiation():
    from backend.models.prospect import Prospect, QualificationEvidence

    ws_id = uuid4()
    icp_id = uuid4()
    prospect_id = uuid4()
    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=icp_id,
        name="Chai Point",
        canonical_category="cafe",
        city="Pune",
        website_url="https://chaipoint.example.com",
        status="QUEUED",
        qualification_status="UNQUALIFIED",
    )
    assert prospect.id == prospect_id
    assert prospect.name == "Chai Point"
    assert prospect.status == "QUEUED"
    assert prospect.qualification_status == "UNQUALIFIED"
    assert Prospect.__tablename__ == "prospects"

    ev_id = uuid4()
    evidence = QualificationEvidence(
        id=ev_id,
        workspace_id=ws_id,
        prospect_id=prospect_id,
        signal_key="web_reachability",
        signal_value={"reachable": True, "http_status": 200},
        confidence=1.0,
        source_url="https://chaipoint.example.com",
    )
    assert evidence.id == ev_id
    assert evidence.signal_key == "web_reachability"
    assert evidence.confidence == 1.0
    assert QualificationEvidence.__tablename__ == "qualification_evidence"
