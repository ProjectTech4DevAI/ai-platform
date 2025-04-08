from uuid import UUID, uuid4
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.util import now


class Collection(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )
    llm_service_id: str
    llm_service_name: str
    created_at: datetime = Field(
        default_factory=now,
    )
    deleted_at: datetime | None
