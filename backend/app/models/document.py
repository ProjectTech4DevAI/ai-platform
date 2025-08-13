from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now
from .user import User


class Document(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    owner_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    fname: str
    object_store_url: str
    inserted_at: datetime = Field(
        default_factory=now,
    )
    updated_at: datetime = Field(
        default_factory=now,
    )
    deleted_at: datetime | None
    source_document_id: Optional[UUID] = Field(
        default=None,
        foreign_key="document.id",
        nullable=True,
    )

    owner: User = Relationship(back_populates="documents")
