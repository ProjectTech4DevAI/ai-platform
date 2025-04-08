import enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel, Enum, Column

from app.core.util import now


class LanguageModelService(enum.Enum):
    OPENAI = "open-ai"


class Collection(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    llm_service: LanguageModelService = Field(
        sa_column=Column(Enum(LanguageModelService)),
    )
    llm_service_id: str
    created_at: datetime = Field(
        default_factory=now,
    )
    deleted_at: datetime | None
