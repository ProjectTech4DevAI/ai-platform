from uuid import UUID

from sqlmodel import Field, SQLModel

from app.core.util import now


class DocumentCollection(SQLModel, table=True):
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
