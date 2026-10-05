"""Unit tests for ICP domain service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.middleware.errors import AppError
from backend.models.icp import ICP
from backend.providers.ai.mock import MockAIProvider, get_default_mock_criteria
from backend.schemas.icp import ICPCreate, ICPUpdate
from backend.services.icp import ICPService


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_icp():
    return ICP(
        id=uuid4(),
        workspace_id=uuid4(),
        created_by=uuid4(),
        name="Pune Cafes Lead Engine",
        raw_prompt="I build websites for cafes in Pune without an online presence.",
        status="DRAFT",
        version=1,
        compiled_criteria=None,
        compilation_error=None,
    )


@pytest.mark.anyio
async def test_create_icp_service(mock_db_session):
    workspace_id = uuid4()
    user_id = uuid4()
    create_dto = ICPCreate(
        name="Test ICP",
        raw_prompt="Targeting salons in Mumbai with no website",
    )

    icp = await ICPService.create_icp(mock_db_session, workspace_id, user_id, create_dto)

    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_awaited_once()
    mock_db_session.refresh.assert_awaited_once()
    assert icp.workspace_id == workspace_id
    assert icp.created_by == user_id
    assert icp.name == "Test ICP"
    assert icp.status == "DRAFT"
    assert icp.version == 1


@pytest.mark.anyio
async def test_create_icp_service_empty_fields(mock_db_session):
    workspace_id = uuid4()
    user_id = uuid4()

    with pytest.raises(AppError) as exc_info:
        await ICPService.create_icp(
            mock_db_session, workspace_id, user_id, ICPCreate(name="   ", raw_prompt="valid")
        )
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_get_icp_by_id_found_and_not_found(mock_db_session, sample_icp):
    # Found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_icp
    mock_db_session.execute.return_value = mock_result

    icp = await ICPService.get_icp_by_id(mock_db_session, sample_icp.workspace_id, sample_icp.id)
    assert icp == sample_icp

    # Not found / wrong workspace
    mock_result.scalar_one_or_none.return_value = None
    with pytest.raises(AppError) as exc_info:
        await ICPService.get_icp_by_id(mock_db_session, sample_icp.workspace_id, uuid4())
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_compile_icp_success(mock_db_session, sample_icp):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_icp
    mock_db_session.execute.return_value = mock_result

    mock_ai = MockAIProvider(default_criteria=get_default_mock_criteria(city="Pune"))

    compiled = await ICPService.compile_icp(
        mock_db_session, sample_icp.workspace_id, sample_icp.id, mock_ai
    )

    assert compiled.status == "COMPILED"
    assert compiled.version == 2
    assert compiled.compiled_criteria is not None
    assert compiled.compiled_criteria["location"]["city"] == "Pune"
    assert compiled.compilation_error is None
    mock_db_session.commit.assert_awaited()


@pytest.mark.anyio
async def test_compile_icp_failure_records_error(mock_db_session, sample_icp):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_icp
    mock_db_session.execute.return_value = mock_result

    mock_ai = MockAIProvider(
        error_to_raise=AppError("AI_RATE_LIMIT_EXCEEDED", "Rate limit hit", status_code=429)
    )

    with pytest.raises(AppError) as exc_info:
        await ICPService.compile_icp(
            mock_db_session, sample_icp.workspace_id, sample_icp.id, mock_ai
        )

    assert exc_info.value.code == "AI_RATE_LIMIT_EXCEEDED"
    assert sample_icp.compilation_error == "Rate limit hit"
    mock_db_session.commit.assert_awaited()


@pytest.mark.anyio
async def test_compile_icp_cannot_compile_archived_or_approved(mock_db_session, sample_icp):
    mock_result = MagicMock()
    mock_db_session.execute.return_value = mock_result

    # Archived
    sample_icp.status = "ARCHIVED"
    mock_result.scalar_one_or_none.return_value = sample_icp
    with pytest.raises(AppError) as exc_info:
        await ICPService.compile_icp(
            mock_db_session, sample_icp.workspace_id, sample_icp.id, MockAIProvider()
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"

    # Approved
    sample_icp.status = "APPROVED"
    mock_result.scalar_one_or_none.return_value = sample_icp
    with pytest.raises(AppError) as exc_info:
        await ICPService.compile_icp(
            mock_db_session, sample_icp.workspace_id, sample_icp.id, MockAIProvider()
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"


@pytest.mark.anyio
async def test_update_icp_name_and_prompt_reverts_compiled_to_draft(mock_db_session, sample_icp):
    sample_icp.status = "COMPILED"
    sample_icp.version = 2
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_icp
    mock_db_session.execute.return_value = mock_result

    update_dto = ICPUpdate(
        name="Updated Name",
        raw_prompt="New prompt targeting bakeries in Bangalore",
    )

    updated = await ICPService.update_icp(
        mock_db_session, sample_icp.workspace_id, sample_icp.id, update_dto, user_role="member"
    )

    assert updated.name == "Updated Name"
    assert updated.raw_prompt == "New prompt targeting bakeries in Bangalore"
    assert updated.status == "DRAFT"  # Reverted back to DRAFT!
    assert updated.version == 3


@pytest.mark.anyio
async def test_update_icp_state_transitions(mock_db_session, sample_icp):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_icp
    mock_db_session.execute.return_value = mock_result

    # 1. COMPILED -> APPROVED (without compiled criteria -> fails)
    sample_icp.status = "COMPILED"
    sample_icp.compiled_criteria = None
    with pytest.raises(AppError) as exc_info:
        await ICPService.update_icp(
            mock_db_session,
            sample_icp.workspace_id,
            sample_icp.id,
            ICPUpdate(status="APPROVED"),
            user_role="member",
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"

    # 2. COMPILED -> APPROVED (with compiled criteria -> succeeds)
    sample_icp.compiled_criteria = {"service": "web"}
    approved = await ICPService.update_icp(
        mock_db_session,
        sample_icp.workspace_id,
        sample_icp.id,
        ICPUpdate(status="APPROVED"),
        user_role="member",
    )
    assert approved.status == "APPROVED"

    # 3. APPROVED -> ARCHIVED by member (fails with 403 FORBIDDEN_OPERATION)
    with pytest.raises(AppError) as exc_info:
        await ICPService.update_icp(
            mock_db_session,
            sample_icp.workspace_id,
            sample_icp.id,
            ICPUpdate(status="ARCHIVED"),
            user_role="member",
        )
    assert exc_info.value.code == "FORBIDDEN_OPERATION"
    assert exc_info.value.status_code == 403

    # 4. APPROVED -> ARCHIVED by owner (succeeds)
    archived = await ICPService.update_icp(
        mock_db_session,
        sample_icp.workspace_id,
        sample_icp.id,
        ICPUpdate(status="ARCHIVED"),
        user_role="owner",
    )
    assert archived.status == "ARCHIVED"

    # 5. Modifying ARCHIVED ICP (fails with 409)
    with pytest.raises(AppError) as exc_info:
        await ICPService.update_icp(
            mock_db_session,
            sample_icp.workspace_id,
            sample_icp.id,
            ICPUpdate(name="Try updating archived"),
            user_role="owner",
        )
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"
    assert exc_info.value.status_code == 409
