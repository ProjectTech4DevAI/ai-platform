from typing import Optional
from uuid import UUID
from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON

from app.core.util import now


class EvaluationStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ModelEvaluationBase(SQLModel):
    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
    )

    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )

    eval_split_ratio: list[float] = Field(sa_column=Column(JSON, nullable=False))
    metric: str = Field(
        nullable=False, description="Metric used for evaluation (e.g., mcc)"
    )


class ModelEvaluationCreate(ModelEvaluationBase):
    pass


class Model_Evaluation(ModelEvaluationBase, table=True):
    """Database model for keeping a record of model evaluation"""

    id: int = Field(primary_key=True)

    fine_tuning_id: int = Field(
        foreign_key="fine_tuning.id",
        nullable=False,
        ondelete="CASCADE",
    )

    score: float = Field(nullable=True, description="Matthews Correlation Coefficient")
    status: EvaluationStatus = Field(
        default=EvaluationStatus.pending, description="Evaluation status"
    )

    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    deleted_at: datetime | None = Field(default=None, nullable=True)

    project: "Project" = Relationship(back_populates="model_evaluation")
    organization: "Organization" = Relationship(back_populates="model_evaluation")
    fine_tuning: "Fine_Tuning" = Relationship(back_populates="model_evaluation")


class ModelEvaluationPublic(ModelEvaluationBase):
    """Public response model for evaluation result."""

    id: int
    fine_tuning_id: int
    metric: str
    score: float | None = None
    status: EvaluationStatus
    inserted_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
