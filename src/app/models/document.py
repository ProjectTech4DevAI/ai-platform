from uuid import UUID, uuid4
from datetime import datetime, UTC
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: int | None = Field(default=None, primary_key=True)
    fname_external: str = Field(max_length=512)
    object_store_url: str = Field(max_length=2083)
    owner: int | None = Field(default=None, foreign_key="user.id", index=True)
    fname_internal: UUID = Field(
        default_factory=uuid4,
        index=True,
        unique=True
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True)
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True)
    )
    is_deleted: bool = Field(default=False, index=True)
