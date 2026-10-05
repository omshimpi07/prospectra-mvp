"""Prospect and QualificationEvidence SQLAlchemy models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from backend.models.icp import ICP
    from backend.models.profile import Profile
    from backend.models.search import SearchResult
    from backend.models.workspace import Workspace


class Prospect(Base, TimestampMixin):
    """Candidate promoted into the workspace qualification pipeline."""

    __tablename__ = "prospects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED', 'RESEARCHING', 'COMPLETED', 'FAILED')",
            name="chk_prospect_status",
        ),
        CheckConstraint(
            "qualification_status IN ('UNQUALIFIED', 'QUALIFIED', 'DISQUALIFIED', 'REVIEW_NEEDED')",
            name="chk_qualification_status",
        ),
        CheckConstraint(
            "priority_score >= 0.0 AND priority_score <= 1.0",
            name="chk_prospect_priority_score",
        ),
        CheckConstraint(
            "review_status IN ('UNREVIEWED', 'APPROVED', 'REJECTED')",
            name="chk_prospect_review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    icp_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("icps.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    search_result_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("search_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_category: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="QUEUED", index=True)
    qualification_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNQUALIFIED", index=True
    )
    fit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    scoring_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_signals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Sprint 6: Human Review State
    review_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UNREVIEWED", index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship("Workspace")
    icp: Mapped["ICP"] = relationship("ICP")
    search_result: Mapped["SearchResult | None"] = relationship("SearchResult")
    reviewer: Mapped["Profile | None"] = relationship("Profile", foreign_keys=[reviewed_by])
    evidence: Mapped[list["QualificationEvidence"]] = relationship(
        "QualificationEvidence", back_populates="prospect", cascade="all, delete-orphan"
    )


class QualificationEvidence(Base):
    """Atomic, auditable technical or business observation supporting qualification."""

    __tablename__ = "qualification_evidence"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prospect_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("prospects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_key: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    prospect: Mapped[Prospect] = relationship("Prospect", back_populates="evidence")
