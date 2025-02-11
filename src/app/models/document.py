import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db.database import Base

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
    owner: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), # XXX Does user correspond to client-project?
        index=True,
        default=None,
        init=False,
    )

    #
    # Data representation
    #
    fname_internal: Mapped[uuid.UUID] = mapped_column(
        default_factory=uuid.uuid4,
        primary_key=True,
        unique=True,
    )
    fname_external: Mapped[str] = mapped_column(String(512))
    object_store_url: Mapped[str] = mapped_column(String(2048))

    #
    # Record management
    #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=datetime.utcnow,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
