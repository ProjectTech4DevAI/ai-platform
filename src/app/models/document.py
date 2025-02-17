import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base

def now():
    return (datetime
            .now(timezone.utc)
            .replace(tzinfo=None))

#
#
#
class Document(Base):
    __tablename__ = "document"

    #
    # Keys
    #
    id: Mapped[int] = mapped_column(
        "id",
        autoincrement=True,
        nullable=False,
        unique=True,
        primary_key=True,
        init=False,
    )
    owner: Mapped[int] = mapped_column(
        ForeignKey("user.id"), # XXX Does user correspond to client-project?
        index=True,
        default=None,
        init=False,
    )

    #
    # Data representation
    #
    fname_internal: Mapped[uuid.UUID] = mapped_column(
        index=True,
        unique=True,
        default_factory=uuid.uuid4,
    )
    fname_external: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    object_store_url: Mapped[str] = mapped_column(String(2083))

    #
    # Record management
    #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=now,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )

    # Enable CRUD soft delete
    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        index=True,
    )
