import enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import SQLModel, Field
from pydantic import ConfigDict

from app.core.util import now


class TransformationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocTransformationJob(SQLModel, table=True):
    __tablename__ = "doc_transformation_job"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_document_id: UUID = Field(foreign_key="document.id")
    transformed_document_id: UUID | None = Field(
        default=None, foreign_key="document.id"
    )
    status: TransformationStatus = Field(default=TransformationStatus.PENDING)
    task_id: str | None = Field(default=None, nullable=True)
    trace_id: str | None = Field(
        default=None, description="Tracing ID for correlating logs and traces."
    )
    error_message: str | None = Field(default=None)
    inserted_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @property
    def job_id(self) -> UUID:
        return self.id

    @property
    def job_inserted_at(self) -> datetime:
        return self.inserted_at

    @property
    def job_updated_at(self) -> datetime:
        return self.updated_at


class DocTransformJobCreate(SQLModel):
    source_document_id: UUID

    model_config = ConfigDict(extra="forbid")


class DocTransformJobUpdate(SQLModel):
    transformed_document_id: UUID | None = None
    task_id: str | None = None
    status: TransformationStatus | None = None
    error_message: str | None = None
    trace_id: str | None = None
