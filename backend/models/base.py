"""SQLAlchemy 2.x declarative base shared by all future models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Adds timezone-aware ``created_at`` / ``updated_at`` columns.

    Values are set in Python (UTC) by the ORM; ``server_default`` covers rows
    inserted outside the ORM. ``updated_at`` is refreshed on ORM updates only.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
