"""Unit tests for WorkspaceService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.models.base import utc_now
from backend.models.workspace import Workspace, WorkspaceMember
from backend.schemas.workspace import WorkspaceCreate
from backend.services.workspace import WorkspaceService, slugify


def test_slugify():
    assert slugify("Acme Agency") == "acme-agency"
    assert slugify("  Acme & Sons!  ") == "acme-sons"
    assert slugify("!!!") == "workspace"


def test_create_workspace_service():
    user_id = uuid4()
    data = WorkspaceCreate(name="Growth Marketers")

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    # Check slug collision query returns None
    mock_check_res = MagicMock()
    mock_check_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_check_res

    res = asyncio.run(WorkspaceService.create_workspace(mock_db, user_id, data))

    assert res.name == "Growth Marketers"
    assert res.slug == "growth-marketers"
    assert res.role == "owner"
    assert res.created_by == user_id
    assert mock_db.add.call_count == 2  # Workspace + WorkspaceMember
    assert mock_db.commit.call_count == 1


def test_get_user_workspaces_service():
    user_id = uuid4()
    now = utc_now()
    ws1 = Workspace(
        id=uuid4(), name="WS1", slug="ws1", created_by=user_id, created_at=now, updated_at=now
    )
    ws2 = Workspace(
        id=uuid4(), name="WS2", slug="ws2", created_by=user_id, created_at=now, updated_at=now
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.all.return_value = [(ws1, "owner"), (ws2, "member")]
    mock_db.execute.return_value = mock_res

    res = asyncio.run(WorkspaceService.get_user_workspaces(mock_db, user_id))

    assert len(res) == 2
    assert res[0].name == "WS1"
    assert res[0].role == "owner"
    assert res[1].name == "WS2"
    assert res[1].role == "member"


def test_get_workspace_members_service():
    ws_id = uuid4()
    user_id = uuid4()
    now = utc_now()
    member = WorkspaceMember(
        id=uuid4(), workspace_id=ws_id, user_id=user_id, role="owner", joined_at=now
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.all.return_value = [(member, "user@example.com", "User Name")]
    mock_db.execute.return_value = mock_res

    members = asyncio.run(WorkspaceService.get_workspace_members(mock_db, ws_id))

    assert len(members) == 1
    assert members[0].user_id == user_id
    assert members[0].email == "user@example.com"
    assert members[0].role == "owner"
