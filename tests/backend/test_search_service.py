"""Unit tests for Search domain service and async worker."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.middleware.errors import AppError
from backend.models.base import utc_now
from backend.models.icp import ICP
from backend.models.search import Search
from backend.providers.discovery.mock import MockDiscoveryProvider
from backend.schemas.search import SearchCreate
from backend.services.search import SearchService
from backend.services.search_worker import SearchWorker


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def approved_icp():
    now = utc_now()
    return ICP(
        id=uuid4(),
        workspace_id=uuid4(),
        created_by=uuid4(),
        name="Pune Cafes ICP",
        raw_prompt="I target cafes in Pune",
        status="APPROVED",
        version=2,
        compiled_criteria={
            "service_offering": "Website Development",
            "target_categories": ["cafe", "bakery"],
            "location": {
                "city": "Pune",
                "state_province": "Maharashtra",
                "country": "IN",
                "radius_km": 20.0,
            },
        },
        created_at=now,
        updated_at=now,
    )


@pytest.mark.anyio
async def test_create_search_from_approved_icp(mock_db_session, approved_icp):
    user_id = uuid4()
    mock_res_icp = MagicMock()
    mock_res_icp.scalar_one_or_none.return_value = approved_icp

    mock_db_session.execute.return_value = mock_res_icp

    data = SearchCreate(icp_id=approved_icp.id, radius_km=20.0, limit=50)

    search = await SearchService.create_search(
        mock_db_session, approved_icp.workspace_id, user_id, data
    )

    assert search.workspace_id == approved_icp.workspace_id
    assert search.icp_id == approved_icp.id
    assert search.status == "CREATED"
    assert search.specification["city"] == "Pune"
    assert search.specification["target_categories"] == ["cafe", "bakery"]
    assert "bounding_box" in search.specification
    assert search.queued_at is None
    assert search.started_at is None


@pytest.mark.anyio
async def test_create_search_rejects_unapproved_icp(mock_db_session, approved_icp):
    approved_icp.status = "COMPILED"  # Not yet APPROVED
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = approved_icp
    mock_db_session.execute.return_value = mock_res

    data = SearchCreate(icp_id=approved_icp.id)

    with pytest.raises(AppError) as exc_info:
        await SearchService.create_search(mock_db_session, approved_icp.workspace_id, uuid4(), data)
    assert exc_info.value.code == "INVALID_ICP_STATUS"
    assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_create_search_rejects_unsupported_city(mock_db_session, approved_icp):
    approved_icp.compiled_criteria["location"]["city"] = "Atlantis"
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = approved_icp
    mock_db_session.execute.return_value = mock_res

    data = SearchCreate(icp_id=approved_icp.id)

    with pytest.raises(AppError) as exc_info:
        await SearchService.create_search(mock_db_session, approved_icp.workspace_id, uuid4(), data)
    assert exc_info.value.code == "UNSUPPORTED_CITY"
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_queue_search_state_transition(mock_db_session):
    now = utc_now()
    ws_id = uuid4()
    search = Search(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        created_by=uuid4(),
        status="CREATED",
        specification={"city": "Pune"},
        created_at=now,
        updated_at=now,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = search
    mock_db_session.execute.return_value = mock_res

    queued = await SearchService.queue_search(mock_db_session, ws_id, search.id)

    assert queued.status == "QUEUED"
    assert queued.queued_at is not None
    assert queued.started_at is None  # started_at not yet set


@pytest.mark.anyio
async def test_queue_search_already_running_rejected(mock_db_session):
    now = utc_now()
    ws_id = uuid4()
    search = Search(
        id=uuid4(),
        workspace_id=ws_id,
        icp_id=uuid4(),
        created_by=uuid4(),
        status="RUNNING",
        specification={"city": "Pune"},
        created_at=now,
        updated_at=now,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = search
    mock_db_session.execute.return_value = mock_res

    with pytest.raises(AppError) as exc_info:
        await SearchService.queue_search(mock_db_session, ws_id, search.id)
    assert exc_info.value.code == "INVALID_STATE_TRANSITION"
    assert exc_info.value.status_code == 409


@pytest.mark.anyio
async def test_execute_search_success(mock_db_session):
    now = utc_now()
    ws_id = uuid4()
    search_id = uuid4()
    claimed_search = Search(
        id=search_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        created_by=uuid4(),
        status="RUNNING",
        specification={
            "target_categories": ["cafe"],
            "city": "Pune",
            "center_lat": 18.5204,
            "center_lon": 73.8567,
            "radius_km": 15.0,
            "bounding_box": {
                "min_lat": 18.4,
                "max_lat": 18.6,
                "min_lon": 73.7,
                "max_lon": 73.9,
            },
            "limit": 10,
        },
        created_at=now,
        updated_at=now,
    )
    mock_claim_res = MagicMock()
    mock_claim_res.scalar_one_or_none.return_value = claimed_search
    mock_db_session.execute.return_value = mock_claim_res

    provider = MockDiscoveryProvider()
    completed = await SearchService.execute_search(mock_db_session, search_id, provider)

    assert completed.status == "COMPLETED"
    assert completed.total_candidates > 0
    assert completed.finished_at is not None
    mock_db_session.add_all.assert_called_once()


@pytest.mark.anyio
async def test_execute_search_failure(mock_db_session):
    now = utc_now()
    ws_id = uuid4()
    search_id = uuid4()
    claimed_search = Search(
        id=search_id,
        workspace_id=ws_id,
        icp_id=uuid4(),
        created_by=uuid4(),
        status="RUNNING",
        specification={
            "target_categories": ["cafe"],
            "city": "Pune",
            "center_lat": 18.5204,
            "center_lon": 73.8567,
            "radius_km": 15.0,
            "bounding_box": {
                "min_lat": 18.4,
                "max_lat": 18.6,
                "min_lon": 73.7,
                "max_lon": 73.9,
            },
            "limit": 10,
        },
        created_at=now,
        updated_at=now,
    )
    mock_claim_res = MagicMock()
    mock_claim_res.scalar_one_or_none.return_value = claimed_search
    mock_db_session.execute.return_value = mock_claim_res

    provider = MockDiscoveryProvider(
        error_to_raise=AppError(
            "DISCOVERY_PROVIDER_TIMEOUT", "Remote query timed out", status_code=504
        )
    )
    failed = await SearchService.execute_search(mock_db_session, search_id, provider)

    assert failed.status == "FAILED"
    assert failed.error_code == "DISCOVERY_PROVIDER_TIMEOUT"
    assert "Remote query timed out" in (failed.error_message or "")


@pytest.mark.anyio
async def test_search_worker_stale_recovery(mock_db_session):
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db_session
    mock_session_factory.return_value.__aexit__ = AsyncMock()

    mock_res = MagicMock()
    mock_res.rowcount = 2
    mock_db_session.execute.return_value = mock_res

    worker = SearchWorker(
        session_factory=mock_session_factory,
        discovery_provider=MockDiscoveryProvider(),
        job_timeout_seconds=300.0,
    )
    recovered = await worker.recover_stale_searches()
    assert recovered == 2
    mock_db_session.commit.assert_awaited()


@pytest.mark.anyio
async def test_search_worker_process_batch_empty(mock_db_session):
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db_session
    mock_session_factory.return_value.__aexit__ = AsyncMock()

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_res

    worker = SearchWorker(
        session_factory=mock_session_factory,
        discovery_provider=MockDiscoveryProvider(),
    )
    processed = await worker.process_next_batch()
    assert processed == 0


@pytest.mark.anyio
async def test_search_worker_process_batch_fault_isolation(mock_db_session, monkeypatch):
    search1_id = uuid4()
    search2_id = uuid4()

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db_session
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    # 1. First call to execute returns the 2 queued IDs
    mock_res_ids = MagicMock()
    mock_res_ids.scalars.return_value.all.return_value = [search1_id, search2_id]

    # For subsequent update calls
    mock_res_update = MagicMock()
    mock_res_update.rowcount = 1

    mock_db_session.execute.side_effect = [
        mock_res_ids,  # Initial query for queued IDs
        mock_res_update,  # Fallback update for search1
    ]

    executed_ids: list[object] = []

    async def mock_execute_search(session, s_id, provider):
        executed_ids.append(s_id)
        if s_id == search1_id:
            raise RuntimeError("Simulated unhandled search execution error")
        return MagicMock()

    monkeypatch.setattr(SearchService, "execute_search", mock_execute_search)

    worker = SearchWorker(
        session_factory=mock_session_factory,
        discovery_provider=MockDiscoveryProvider(),
    )
    worker._is_running = True

    processed = await worker.process_next_batch()

    # Both searches were processed despite search1 raising an error
    assert processed == 2
    assert executed_ids == [search1_id, search2_id]
    # Commit was called during fallback update
    mock_db_session.commit.assert_awaited()
