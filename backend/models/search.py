"""Search and SearchResult SQLAlchemy models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from backend.models.icp import ICP
    from backend.models.profile import Profile
    from backend.models.workspace import Workspace


class Search(Base, TimestampMixin):
    """Search execution entity initiated from an APPROVED ICP."""

    __tablename__ = "searches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="chk_search_status",
        ),
        UniqueConstraint("workspace_id", "idempotency_key", name="uq_workspace_idempotency"),
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
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="CREATED", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship("Workspace")
    icp: Mapped["ICP"] = relationship("ICP")
    creator: Mapped["Profile"] = relationship("Profile")
    results: Mapped[list["SearchResult"]] = relationship(
        "SearchResult", back_populates="search", cascade="all, delete-orphan"
    )


class SearchResult(Base):
    """Canonical representation of a discovered business candidate."""

    __tablename__ = "search_results"
    __table_args__ = (UniqueConstraint("search_id", "external_id", name="uq_search_external_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    search_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("searches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="overture")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_category: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    search: Mapped[Search] = relationship("Search", back_populates="results")
