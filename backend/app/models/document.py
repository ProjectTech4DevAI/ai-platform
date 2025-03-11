from uuid import UUID, uuid4
from pathlib import Path
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from .user import User

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Document(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    owner_id: UUID = Field(
        foreign_key='user.id',
        nullable=False,
        ondelete='CASCADE',
    )
    fname_external: Path
    fname_internal: Path
    object_store_url: str
    created_at: datetime = Field(
        default_factory=now,
    )
    updated_at: datetime | None
    deleted_at: datetime | None

    owner: User = Relationship(back_populates='documents')

class DocumentList(SQLModel):
    docs: list[Document]

    def __len__(self):
        return len(self.docs)
