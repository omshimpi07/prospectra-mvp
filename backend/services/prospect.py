"""Prospect domain service."""

import logging
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.middleware.errors import AppError
from backend.models.base import utc_now
from backend.models.icp import ICP
from backend.models.prospect import Prospect, QualificationEvidence
from backend.models.search import SearchResult
from backend.providers.ai.base import AIProvider
from backend.providers.web.extractors import extract_signals_from_page
from backend.providers.web.fetcher import SecureWebFetcher
from backend.schemas.icp import CompiledICPCriteria
from backend.schemas.prospect import QualifyCandidatesResponse
from backend.services.qualification import QualificationEngine

logger = logging.getLogger(__name__)


class ProspectService:
    """Service managing prospect promotion, research execution, and evidence storage."""

    @staticmethod
    async def qualify_candidates(
        db: AsyncSession,
        workspace_id: UUID,
        search_result_ids: list[UUID],
    ) -> QualifyCandidatesResponse:
        """Promote discovered search results into the qualification pipeline."""
        now = utc_now()

        # Fetch search results with their parent search (to access icp_id)
        stmt = (
            select(SearchResult)
            .options(selectinload(SearchResult.search))
            .where(
                SearchResult.id.in_(search_result_ids),
                SearchResult.workspace_id == workspace_id,
            )
        )
        res = await db.execute(stmt)
        candidates = list(res.scalars().all())

        if not candidates:
            raise AppError(
                "NOT_FOUND", "No valid candidates found for qualification.", status_code=404
            )

        # Check existing prospects for these search results
        existing_stmt = select(Prospect).where(
            Prospect.workspace_id == workspace_id,
            Prospect.search_result_id.in_([c.id for c in candidates]),
        )
        existing_res = await db.execute(existing_stmt)
        existing_map = {p.search_result_id: p for p in existing_res.scalars().all()}

        prospect_ids: list[UUID] = []
        new_prospects: list[Prospect] = []

        for candidate in candidates:
            existing = existing_map.get(candidate.id)
            if existing:
                # If existing prospect failed or was finished, requeue it
                if existing.status in ("FAILED", "COMPLETED"):
                    existing.status = "QUEUED"
                    existing.qualification_status = "UNQUALIFIED"
                    existing.queued_at = now
                    existing.error_code = None
                    existing.error_message = None
                    existing.updated_at = now
                prospect_ids.append(existing.id)
            else:
                p = Prospect(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    icp_id=candidate.search.icp_id,
                    search_result_id=candidate.id,
                    name=candidate.name,
                    canonical_category=candidate.canonical_category,
                    city=candidate.city,
                    website_url=candidate.website,
                    phone=candidate.phone,
                    status="QUEUED",
                    qualification_status="UNQUALIFIED",
                    fit_score=0.0,
                    queued_at=now,
                    created_at=now,
                    updated_at=now,
                )
                new_prospects.append(p)
                prospect_ids.append(p.id)

        if new_prospects:
            db.add_all(new_prospects)

        await db.commit()
        return QualifyCandidatesResponse(
            enqueued_count=len(prospect_ids),
            prospect_ids=prospect_ids,
            message=f"Enqueued {len(prospect_ids)} candidate(s) for qualification research.",
        )

    @staticmethod
    async def list_prospects(
        db: AsyncSession,
        workspace_id: UUID,
        qualification_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Prospect]:
        """List prospects in workspace with optional qualification status filter."""
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        stmt = (
            select(Prospect)
            .where(Prospect.workspace_id == workspace_id)
            .order_by(Prospect.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if qualification_status:
            stmt = stmt.where(Prospect.qualification_status == qualification_status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_prospect_by_id(
        db: AsyncSession,
        workspace_id: UUID,
        prospect_id: UUID,
    ) -> Prospect:
        """Retrieve a prospect by ID with workspace isolation."""
        stmt = select(Prospect).where(
            Prospect.id == prospect_id,
            Prospect.workspace_id == workspace_id,
        )
        result = await db.execute(stmt)
        prospect = result.scalar_one_or_none()
        if not prospect:
            raise AppError(
                "PROSPECT_NOT_FOUND", "Prospect not found in workspace.", status_code=404
            )
        return prospect

    @staticmethod
    async def list_evidence(
        db: AsyncSession,
        workspace_id: UUID,
        prospect_id: UUID,
    ) -> list[QualificationEvidence]:
        """List auditable evidence items supporting a prospect's qualification."""
        # Ensure prospect exists and belongs to workspace
        await ProspectService.get_prospect_by_id(db, workspace_id, prospect_id)

        stmt = (
            select(QualificationEvidence)
            .where(
                QualificationEvidence.prospect_id == prospect_id,
                QualificationEvidence.workspace_id == workspace_id,
            )
            .order_by(QualificationEvidence.created_at.asc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def requalify_prospect(
        db: AsyncSession,
        workspace_id: UUID,
        prospect_id: UUID,
    ) -> Prospect:
        """Re-enqueue an existing prospect for research and qualification."""
        prospect = await ProspectService.get_prospect_by_id(db, workspace_id, prospect_id)

        now = utc_now()
        prospect.status = "QUEUED"
        prospect.qualification_status = "UNQUALIFIED"
        prospect.queued_at = now
        prospect.error_code = None
        prospect.error_message = None
        prospect.updated_at = now

        await db.commit()
        await db.refresh(prospect)
        return prospect

    @staticmethod
    async def execute_prospect_research(
        db: AsyncSession,
        prospect_id: UUID,
        fetcher: SecureWebFetcher,
        ai_provider: AIProvider | None = None,
    ) -> Prospect:
        """Atomically claim a QUEUED prospect, execute web research, extract evidence, and qualify."""
        now = utc_now()

        # Atomic claim: QUEUED -> RESEARCHING
        stmt_claim = (
            update(Prospect)
            .where(Prospect.id == prospect_id, Prospect.status == "QUEUED")
            .values(status="RESEARCHING", started_at=now, updated_at=now)
            .returning(Prospect)
        )
        res_claim = await db.execute(stmt_claim)
        prospect = res_claim.scalar_one_or_none()
        await db.commit()

        if not prospect:
            # Already claimed or no longer QUEUED
            stmt_curr = select(Prospect).where(Prospect.id == prospect_id)
            res_curr = await db.execute(stmt_curr)
            return res_curr.scalar_one()

        try:
            # 1. Fetch associated ICP criteria
            icp_stmt = select(ICP).where(ICP.id == prospect.icp_id)
            icp_res = await db.execute(icp_stmt)
            icp = icp_res.scalar_one()
            icp_criteria = CompiledICPCriteria.model_validate(icp.compiled_criteria)

            # 2. Fetch and extract signals
            website_url = prospect.website_url
            if website_url:
                page = await fetcher.fetch(website_url)
                signals = extract_signals_from_page(page)
                if page.error:
                    signals["error"] = page.error
            else:
                signals = {
                    "website_exists": False,
                    "dns_resolves": None,
                    "reachable": None,
                    "http_status": None,
                    "response_time_ms": None,
                    "https_enforced": False,
                    "ssl_valid": None,
                    "ssl_days_remaining": None,
                    "mobile_viewport": None,
                    "page_title": None,
                    "meta_description": None,
                    "cms_platform": None,
                    "public_emails": [],
                    "public_phones": [prospect.phone] if prospect.phone else [],
                    "social_links": {},
                }

            signals["canonical_category"] = prospect.canonical_category

            # 3. Create Evidence Items
            evidence_items: list[QualificationEvidence] = []
            ev_now = utc_now()

            if website_url:
                evidence_items.append(
                    QualificationEvidence(
                        id=uuid4(),
                        workspace_id=prospect.workspace_id,
                        prospect_id=prospect.id,
                        signal_key="web_reachability",
                        signal_value={
                            "reachable": signals.get("reachable"),
                            "status_code": signals.get("http_status"),
                            "dns_resolves": signals.get("dns_resolves"),
                            "response_time_ms": signals.get("response_time_ms"),
                        },
                        confidence=1.0,
                        source_url=website_url,
                        snippet=f"HTTP Status {signals.get('http_status')}, Reachable={signals.get('reachable')}",
                        observed_at=ev_now,
                        created_at=ev_now,
                    )
                )
                if signals.get("ssl_valid") is not None:
                    evidence_items.append(
                        QualificationEvidence(
                            id=uuid4(),
                            workspace_id=prospect.workspace_id,
                            prospect_id=prospect.id,
                            signal_key="ssl_security",
                            signal_value={
                                "ssl_valid": signals.get("ssl_valid"),
                                "ssl_days_remaining": signals.get("ssl_days_remaining"),
                                "https_enforced": signals.get("https_enforced"),
                            },
                            confidence=1.0,
                            source_url=website_url,
                            snippet=f"SSL Valid={signals.get('ssl_valid')}, Days Remaining={signals.get('ssl_days_remaining')}",
                            observed_at=ev_now,
                            created_at=ev_now,
                        )
                    )
                if signals.get("mobile_viewport") is not None:
                    evidence_items.append(
                        QualificationEvidence(
                            id=uuid4(),
                            workspace_id=prospect.workspace_id,
                            prospect_id=prospect.id,
                            signal_key="mobile_readiness",
                            signal_value={"mobile_viewport": signals.get("mobile_viewport")},
                            confidence=1.0,
                            source_url=website_url,
                            snippet=f"Viewport tag present: {signals.get('mobile_viewport')}",
                            observed_at=ev_now,
                            created_at=ev_now,
                        )
                    )
                if signals.get("cms_platform"):
                    evidence_items.append(
                        QualificationEvidence(
                            id=uuid4(),
                            workspace_id=prospect.workspace_id,
                            prospect_id=prospect.id,
                            signal_key="cms_platform",
                            signal_value={"cms": signals.get("cms_platform")},
                            confidence=1.0,
                            source_url=website_url,
                            snippet=f"Detected CMS: {signals.get('cms_platform')}",
                            observed_at=ev_now,
                            created_at=ev_now,
                        )
                    )

            if (
                signals.get("public_emails")
                or signals.get("public_phones")
                or signals.get("social_links")
            ):
                evidence_items.append(
                    QualificationEvidence(
                        id=uuid4(),
                        workspace_id=prospect.workspace_id,
                        prospect_id=prospect.id,
                        signal_key="public_contacts",
                        signal_value={
                            "emails": signals.get("public_emails"),
                            "phones": signals.get("public_phones"),
                            "socials": signals.get("social_links"),
                        },
                        confidence=1.0,
                        source_url=website_url,
                        snippet=f"Emails: {len(signals.get('public_emails', []))}, Phones: {len(signals.get('public_phones', []))}",
                        observed_at=ev_now,
                        created_at=ev_now,
                    )
                )

            if evidence_items:
                db.add_all(evidence_items)

            # 4. Deterministic Qualification Evaluation
            outcome = QualificationEngine.evaluate(
                icp=icp_criteria,
                signals=signals,
                canonical_category=prospect.canonical_category,
                business_name=prospect.name,
            )

            # 5. Non-critical AI Rationale Synthesis
            rationale = await QualificationEngine.synthesize_rationale(
                icp=icp_criteria,
                signals=signals,
                outcome=outcome,
                ai_provider=ai_provider,
            )

            # 6. Finalize Prospect
            fin_now = utc_now()
            prospect.status = "COMPLETED"
            prospect.qualification_status = outcome.status
            prospect.fit_score = outcome.fit_score
            prospect.qualification_reason = rationale
            prospect.raw_signals = signals
            prospect.qualified_at = fin_now
            prospect.updated_at = fin_now

            await db.commit()
            await db.refresh(prospect)
            return prospect

        except Exception as exc:
            logger.exception("Error executing research for prospect %s: %s", prospect_id, exc)
            fin_now = utc_now()
            prospect.status = "FAILED"
            prospect.error_code = getattr(exc, "code", "RESEARCH_EXECUTION_ERROR")
            prospect.error_message = str(exc)
            prospect.updated_at = fin_now
            await db.commit()
            await db.refresh(prospect)
            return prospect
