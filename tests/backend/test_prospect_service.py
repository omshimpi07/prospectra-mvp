"""Tests for ProspectService and ResearchWorker."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.models.icp import ICP
from backend.models.prospect import Prospect
from backend.models.search import Search, SearchResult
from backend.providers.web.fetcher import FetchedPage
from backend.services.prospect import ProspectService
from backend.services.research_worker import ResearchWorker


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
def test_setup():
    ws_id = uuid4()
    user_id = uuid4()
    icp_id = uuid4()
    search_id = uuid4()
    candidate_id = uuid4()

    search = Search(
        id=search_id,
        workspace_id=ws_id,
        icp_id=icp_id,
        created_by=user_id,
        status="COMPLETED",
        specification={"city": "Pune"},
    )

    candidate = SearchResult(
        id=candidate_id,
        search_id=search_id,
        workspace_id=ws_id,
        external_id="ext-cand-1",
        provider="overture",
        name="Artisan Cafe",
        canonical_category="cafe",
        latitude=18.5204,
        longitude=73.8567,
        website="https://artisancafe.example.com",
        phone="+919876543210",
    )
    candidate.search = search

    icp = ICP(
        id=icp_id,
        workspace_id=ws_id,
        created_by=user_id,
        name="Pune Cafes",
        raw_prompt="Find cafes in Pune",
        status="APPROVED",
        compiled_criteria={
            "service_offering": "Web Design",
            "target_categories": ["cafe"],
            "location": {"city": "Pune"},
            "signals": {"has_website": True},
            "qualification_notes": [],
        },
    )

    return {
        "workspace_id": ws_id,
        "user_id": user_id,
        "icp": icp,
        "search": search,
        "candidate": candidate,
    }


@pytest.mark.anyio
async def test_qualify_candidates_success(mock_db_session, test_setup):
    ws_id = test_setup["workspace_id"]
    candidate = test_setup["candidate"]

    # Mock candidate query result
    mock_cand_res = MagicMock()
    mock_cand_res.scalars.return_value.all.return_value = [candidate]

    # Mock existing prospects query result (none existing)
    mock_exist_res = MagicMock()
    mock_exist_res.scalars.return_value.all.return_value = []

    mock_db_session.execute.side_effect = [mock_cand_res, mock_exist_res]

    response = await ProspectService.qualify_candidates(
        db=mock_db_session,
        workspace_id=ws_id,
        search_result_ids=[candidate.id],
    )

    assert response.enqueued_count == 1
    assert len(response.prospect_ids) == 1
    mock_db_session.add_all.assert_called_once()
    mock_db_session.commit.assert_awaited()


@pytest.mark.anyio
async def test_execute_prospect_research_success(mock_db_session, test_setup):
    prospect_id = uuid4()
    ws_id = test_setup["workspace_id"]
    icp = test_setup["icp"]

    prospect = Prospect(
        id=prospect_id,
        workspace_id=ws_id,
        icp_id=icp.id,
        name="Artisan Cafe",
        canonical_category="cafe",
        city="Pune",
        website_url="https://artisancafe.example.com",
        phone="+919876543210",
        status="RESEARCHING",
        qualification_status="UNQUALIFIED",
    )

    # 1. Claim returns prospect
    mock_claim_res = MagicMock()
    mock_claim_res.scalar_one_or_none.return_value = prospect

    # 2. ICP fetch returns icp
    mock_icp_res = MagicMock()
    mock_icp_res.scalar_one.return_value = icp

    mock_db_session.execute.side_effect = [mock_claim_res, mock_icp_res]

    # Mock WebFetcher
    mock_fetcher = AsyncMock()
    mock_fetcher.fetch.return_value = FetchedPage(
        original_url="https://artisancafe.example.com",
        final_url="https://artisancafe.example.com",
        status_code=200,
        reachable=True,
        text="<html><head><title>Artisan Cafe</title><meta name='viewport' content='width=device-width'></head></html>",
        https_enforced=True,
        ssl_valid=True,
        ssl_days_remaining=90,
        dns_resolves=True,
    )

    completed = await ProspectService.execute_prospect_research(
        db=mock_db_session,
        prospect_id=prospect_id,
        fetcher=mock_fetcher,
    )

    assert completed.status == "COMPLETED"
    assert completed.qualification_status == "QUALIFIED"
    assert completed.fit_score == 1.0
    assert completed.qualified_at is not None
    mock_db_session.add_all.assert_called_once()  # Added evidence items


@pytest.mark.anyio
async def test_research_worker_stale_recovery(mock_db_session):
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_db_session
    mock_session_factory.return_value.__aexit__ = AsyncMock()

    mock_res = MagicMock()
    mock_res.rowcount = 3
    mock_db_session.execute.return_value = mock_res

    worker = ResearchWorker(
        session_factory=mock_session_factory,
        fetcher=AsyncMock(),
        job_timeout_seconds=120.0,
    )
    recovered = await worker.recover_stale_prospects()
    assert recovered == 3
    mock_db_session.commit.assert_awaited()
