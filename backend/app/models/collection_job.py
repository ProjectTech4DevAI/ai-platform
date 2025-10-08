from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Field, SQLModel, Column, Text

from app.core.util import now
from app.models.collection import CollectionPublic


class CollectionJobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class CollectionActionType(str, Enum):
    CREATE = "CREATE"
    DELETE = "DELETE"


class CollectionJobBase(SQLModel):
    action_type: CollectionActionType = Field(
        nullable=False, description="Type of operation"
    )
    collection_id: UUID | None = Field(
        foreign_key="collection.id", nullable=True, ondelete="CASCADE"
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )


class CollectionJob(CollectionJobBase, table=True):
    """Database model for tracking collection operations."""

    __tablename__ = "collection_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    status: CollectionJobStatus = Field(
        default=CollectionJobStatus.PENDING,
        nullable=False,
        description="Current job status",
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


class CollectionJobPublic(SQLModel):
    id: UUID
    action_type: CollectionActionType
    collection_id: UUID | None = None
    status: CollectionJobStatus
    error_message: str | None = None
    inserted_at: datetime
    updated_at: datetime

    collection: CollectionPublic | None = None
