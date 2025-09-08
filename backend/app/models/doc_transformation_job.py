import enum
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
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
    transformed_document_id: Optional[UUID] = Field(
        default=None, foreign_key="document.id"
    )
    task_id: Optional[str] = Field(default=None, description="Celery task ID")
    status: TransformationStatus = Field(default=TransformationStatus.PENDING)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class DocTransformationJobs(SQLModel):
    jobs: list[DocTransformationJob]
    jobs_not_found: list[UUID]
