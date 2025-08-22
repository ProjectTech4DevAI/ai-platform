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


class DocumentPublic(SQLModel):
    id: UUID = Field(
        description="The unique identifier of the document"
    )
    owner_id: int = Field(
        description="The ID of the user who owns the document",
    )
    fname: str = Field(
        description="The original filename of the document"
    )
    inserted_at: datetime = Field(
        description="The timestamp when the document was inserted"
    )
    updated_at: datetime = Field(
        description="The timestamp when the document was last updated"
    )
    source_document_id: UUID | None = Field(
        default=None,
        description="The ID of the source document if this document is a transformation"
    )
    signed_url: str | None = Field(
        default=None,
        description="A signed URL for accessing the document"
    )


class TransformationJobInfo(SQLModel):
    message: str
    job_id: UUID = Field(
        description="The unique identifier of the transformation job"
    )
    source_format: str = Field(
        description="The format of the source document"
    )
    target_format: str = Field(
        description="The format of the target document"
    )
    transformer: str = Field(
        description="The name of the transformer used"
    )
    status_check_url: str = Field(
        description="The URL to check the status of the transformation job"
    )


class DocumentUploadResponse(DocumentPublic):
    transformation_job: TransformationJobInfo | None = None