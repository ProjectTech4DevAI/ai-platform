from uuid import UUID
from pathlib import Path
from datetime import datetime

from sqlmodel import SQLModel


class DocumentBase(SQLModel):
    fname_external: Path
    object_store_url: str


class DocumentCreate(DocumentBase):
    owner: int


class DocumentRead(DocumentBase):
    id: int
    owner: int
    fname_internal: UUID
    created_at: datetime
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    is_deleted: bool = False


class DocumentUpdate(SQLModel):
    fname_external: Path


# For internal operations
class DocumentDelete(SQLModel):
    fname_internal: UUID
