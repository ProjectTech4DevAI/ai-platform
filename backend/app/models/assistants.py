from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.util import now


class AssistantBase(SQLModel):
    assistant_id: str = Field(index=True, unique=True)
    name: str
    instructions: str = Field(sa_column=Column(Text, nullable=False))
    model: str
    vector_store_ids: List[str] = Field(
        default_factory=list, sa_column=Column(ARRAY(String))
    )
    temperature: float = 0.1
    max_num_results: int = 20
    project_id: int = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    organization_id: int = Field(
        foreign_key="organization.id", nullable=False, ondelete="CASCADE"
    )


class Assistant(AssistantBase, table=True):
    __tablename__ = "openai_assistant"

    id: int = Field(default=None, primary_key=True)
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)

    # Relationships
    project: "Project" = Relationship(back_populates="assistants")
    organization: "Organization" = Relationship(back_populates="assistants")
