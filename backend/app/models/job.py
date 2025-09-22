from datetime import datetime
from enum import Enum
from uuid import uuid4, UUID

from sqlmodel import SQLModel, Field
from app.core.util import now


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class JobType(str, Enum):
    RESPONSE = "RESPONSE"


class Job(SQLModel, table=True):
    __tablename__ = "job"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    task_id: str | None = Field(
        nullable=True, description="Celery task ID returned when job is queued."
    )
    trace_id: str | None = Field(
        default=None, description="Tracing ID for correlating logs and traces."
    )
    error_message: str | None = Field(
        default=None, description="Error details if the job fails."
    )
    status: JobStatus = Field(
        default=JobStatus.PENDING, description="Current state of the job."
    )
    job_type: JobType = Field(
        description="Job type or classification (e.g., response job, ingestion job)."
    )
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class JobUpdate(SQLModel):
    status: JobStatus | None = None
    error_message: str | None = None
    task_id: str | None = None
