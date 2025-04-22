from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from app.core.util import now


class Collection(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    owner_id: UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    llm_service_id: str
    llm_service_name: str
    created_at: datetime = Field(
        default_factory=now,
    )
    deleted_at: datetime | None

    owner: User = Relationship(back_populates="documents")
