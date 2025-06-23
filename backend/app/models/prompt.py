from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from app.core.util import now


class Prompt(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE")
    organization_id: int = Field(foreign_key="organization.id", nullable=False, ondelete="CASCADE")
    inserted_at: datetime = Field(default_factory=now, nullable=False)
    updated_at: datetime = Field(default_factory=now, nullable=False)
    