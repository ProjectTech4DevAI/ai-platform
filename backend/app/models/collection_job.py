from enum import Enum
from uuid import UUID
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Text


from app.core.util import now


class CollectionJobStatus(str, Enum):
    processing = "processing"
    successful = "successful"
    failed = "failed"


class CollectionActionType(str, Enum):
    create = "create"
    delete = "delete"


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

    id: UUID = Field(primary_key=True)

    status: CollectionJobStatus = Field(
        default=CollectionJobStatus.processing,
        nullable=False,
        description="Current job status",
    )

    task_id: UUID = Field(nullable=True)

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


class CollectionJobUpdate(SQLModel):
    task_id: UUID | None = None
    status: CollectionJobStatus
    error_message: str | None = None
    collection_id: UUID | None = None

    updated_at: datetime | None = None


class CollectionJobPublic(SQLModel):
    collection_id: UUID | None = None
    status: CollectionJobStatus
    error_message: str | None = None

    inserted_at: datetime
    updated_at: datetime
