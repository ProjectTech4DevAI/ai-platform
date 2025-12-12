from uuid import UUID

from sqlmodel import Field, SQLModel


class DocumentCollection(SQLModel, table=True):
    """Junction table linking documents to collections."""

    id: int | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={
            "comment": "Unique identifier for the document-collection link"
        },
    )
    document_id: UUID = Field(
        foreign_key="document.id",
        nullable=False,
        ondelete="CASCADE",
        sa_column_kwargs={"comment": "Reference to the document"},
    )
    collection_id: UUID = Field(
        foreign_key="collection.id",
        nullable=False,
        ondelete="CASCADE",
        sa_column_kwargs={"comment": "Reference to the collection"},
    )
