from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.util import now


class DocumentBase(SQLModel):
    project_id: int = Field(
        description="The ID of the project to which the document belongs",
        foreign_key="project.id",
        nullable=False,
        ondelete="CASCADE",
    )
    fname: str = Field(description="The original filename of the document")


class Document(DocumentBase, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="The unique identifier of the document",
    )
    object_store_url: str
    inserted_at: datetime = Field(
        default_factory=now, description="The timestamp when the document was inserted"
    )
    updated_at: datetime = Field(
        default_factory=now,
        description="The timestamp when the document was last updated",
    )
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None
    source_document_id: Optional[UUID] = Field(
        default=None,
        foreign_key="document.id",
        nullable=True,
    )


class DocumentPublic(DocumentBase):
    id: UUID = Field(description="The unique identifier of the document")
    signed_url: str | None = Field(
        default=None, description="A signed URL for accessing the document"
    )
    inserted_at: datetime = Field(
        description="The timestamp when the document was inserted"
    )
    updated_at: datetime = Field(
        description="The timestamp when the document was last updated"
    )
