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
