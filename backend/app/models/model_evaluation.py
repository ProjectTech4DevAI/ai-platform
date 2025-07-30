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
    fine_tuning_id: int = Field(
        foreign_key="fine_tuning.id",
        nullable=False,
        ondelete="CASCADE",
    )


class ModelEvaluationCreate(ModelEvaluationBase):
    pass


class Model_Evaluation(ModelEvaluationBase, table=True):
    """Database model for keeping a record of model evaluation"""

    id: int = Field(primary_key=True)

    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
    )
    eval_split_ratio: float = (Field(nullable=False),)
    metric: list[str] = Field(
        sa_column=Column(JSON, nullable=False),
        description="List of metrics used for evaluation (e.g., ['mcc', 'accuracy'])",
    )
    score: Optional[dict[str, float]] = Field(
        sa_column=Column(JSON, nullable=True),
        description="Evaluation scores per metric (e.g., {'mcc': 0.85})",
    )
    status: EvaluationStatus = Field(
        default=EvaluationStatus.pending, description="Evaluation status"
    )
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
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
    score: dict[str, float] | None = None
    status: EvaluationStatus
    inserted_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
