from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Field, SQLModel, Column, Text
from pydantic import ConfigDict

from app.core.util import now
from app.models.collection import CollectionPublic, CollectionIDPublic


class CollectionJobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class CollectionActionType(str, Enum):
    CREATE = "CREATE"
    DELETE = "DELETE"


class CollectionJob(SQLModel, table=True):
    """Database model for tracking collection operations."""

    __tablename__ = "collection_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    status: CollectionJobStatus = Field(
        default=CollectionJobStatus.PENDING,
        nullable=False,
        description="Current job status",
    )
    action_type: CollectionActionType = Field(
        nullable=False, description="Type of operation"
    )
    collection_id: UUID | None = Field(
        foreign_key="collection.id", nullable=True, ondelete="CASCADE"
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    task_id: str = Field(nullable=True)
    trace_id: str | None = Field(
        default=None, description="Tracing ID for correlating logs and traces."
    )

    error_message: str | None = Field(sa_column=Column(Text, nullable=True))
    inserted_at: datetime = Field(
        default_factory=now,
        nullable=False,
        description="When the job record was created",
    )

    updated_at: datetime = Field(
        default_factory=now,
        nullable=False,
        description="Last time the job record was updated",
    )

    @property
    def job_id(self) -> UUID:
        return self.id

    @property
    def job_inserted_at(self) -> datetime:
        return self.inserted_at

    @property
    def job_updated_at(self) -> datetime:
        return self.updated_at


# Request models
class CollectionJobCreate(SQLModel):
    collection_id: UUID | None = None
    status: CollectionJobStatus
    action_type: CollectionActionType
    project_id: int


class CollectionJobUpdate(SQLModel):
    task_id: str | None = None
    status: CollectionJobStatus | None = None
    error_message: str | None = None
    collection_id: UUID | None = None
    trace_id: str | None = None


##Response models
class CollectionJobBasePublic(SQLModel):
    job_id: UUID
    status: CollectionJobStatus


class CollectionJobImmediatePublic(CollectionJobBasePublic):
    job_inserted_at: datetime
    job_updated_at: datetime


class CollectionJobPublic(CollectionJobBasePublic):
    action_type: CollectionActionType
    collection: CollectionPublic | CollectionIDPublic | None = None
    error_message: str | None = None
