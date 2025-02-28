from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(
        "id",
        autoincrement=True,
        nullable=False,
        unique=True,
        primary_key=True,
        init=False,
    )
    fname_external: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    object_store_url: Mapped[str] = mapped_column(String(2083))

    owner: Mapped[int] = mapped_column(
        ForeignKey("user.id"),  # XXX Does user correspond to client-project?
        index=True,
        default=None,
        init=False,
    )

    fname_internal: Mapped[UUID] = mapped_column(
        index=True,
        unique=True,
        default_factory=uuid4,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=now,
    )

    # Enable FastCRUD update/deletion features
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        index=True,
    )
