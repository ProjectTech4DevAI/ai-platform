from uuid import UUID
from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.util import now


class DocumentCollection(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )
    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
    )
    collection_id: UUID = Field(
        foreign_key="collection.id",
        nullable=False,
        ondelete="CASCADE",
    )
