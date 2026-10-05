"""ICP SQLAlchemy model."""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.models.profile import Profile
    from backend.models.workspace import Workspace


class ICP(Base, TimestampMixin):
    """Ideal Customer Profile (ICP) entity defining target business criteria."""

    __tablename__ = "icps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'COMPILED', 'APPROVED', 'ARCHIVED')",
            name="chk_icp_status",
        ),
        CheckConstraint("char_length(trim(name)) > 0", name="chk_icp_name_not_empty"),
        CheckConstraint("char_length(trim(raw_prompt)) > 0", name="chk_icp_raw_prompt_not_empty"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    compiled_criteria: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    compilation_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["Profile"] = relationship("Profile")
